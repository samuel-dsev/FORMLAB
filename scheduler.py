"""
scheduler.py - Automacao de Agendamento de Laboratorios
=========================================================
Formulario: Agendamento de Aula Pratica - Anhanguera Taubate

Funcionalidades:
  - Agendamento de laboratorio (data unica ou aulas semanais)
  - Cancelamento de laboratorio
  - Verificacao de prazo minimo de 7 dias uteis
  - Verificacao de conflito de horario no SQLite
  - E-mails automaticos para professor e administrador

Requisitos:
    pip install schedule gspread google-auth

Execucao:
    python scheduler.py
"""

import time
import logging
import schedule
from datetime import datetime, date, timedelta

import gspread
from google.oauth2.service_account import Credentials

from config import (
    GOOGLE_CREDENTIALS_FILE,
    GOOGLE_SHEET_ID,
    SHEET_WORKSHEET_NAME,
    COLUMN_MAP,
    ADMIN_EMAIL,
    ADMIN_NAME,
    DB_PATH,
    CHECK_INTERVAL_MINUTES,
    EMAIL_TEMPLATES,
    MIN_BUSINESS_DAYS_AHEAD,
    HOLIDAYS,
    WEEKDAY_MAP,
)
from emailer import send_email
from db import (
    init_db,
    is_conflicting,
    save_booking,
    expand_weekly_bookings,
    cancel_booking,
    get_last_processed_row,
    set_last_processed_row,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scheduler.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ─── Utilitarios de data ──────────────────────────────────────────────────────

def is_holiday(d: date) -> bool:
    return d.strftime("%m-%d") in HOLIDAYS


def normalize_header(text: str) -> str:
    normalized = " ".join(str(text).strip().replace("\n", " ").replace("\r", " ").split())
    return normalized.casefold()


NORMALIZED_COLUMN_MAP = {key: normalize_header(value) for key, value in COLUMN_MAP.items()}


def normalize_row_keys(row: dict) -> dict:
    return {normalize_header(key): value for key, value in row.items()}


def count_business_days(start: date, end: date) -> int:
    """Conta dias uteis entre start (exclusive) e end (inclusive)."""
    count = 0
    current = start + timedelta(days=1)
    while current <= end:
        if current.weekday() < 5 and not is_holiday(current):
            count += 1
        current += timedelta(days=1)
    return count


def has_enough_lead_time(booking_date: date) -> bool:
    today = date.today()
    business_days = count_business_days(today, booking_date)
    return business_days >= MIN_BUSINESS_DAYS_AHEAD


# ─── Google Sheets ────────────────────────────────────────────────────────────

def get_sheet_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scopes)
    return gspread.authorize(creds)


def fetch_new_responses(client):
    sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet(SHEET_WORKSHEET_NAME)
    all_rows = sheet.get_all_records()
    normalized_rows = [normalize_row_keys(row) for row in all_rows]
    last_row = get_last_processed_row()
    new_rows = normalized_rows[last_row:]
    log.info(f"{len(new_rows)} nova(s) resposta(s) encontrada(s).")
    return new_rows, last_row


# ─── Parser de linha ──────────────────────────────────────────────────────────

def parse_row(row: dict) -> dict:
    col = NORMALIZED_COLUMN_MAP

    # Trata data no formato DD/MM/YYYY ou YYYY-MM-DD
    raw_date = str(row.get(col["date"], "")).strip()
    try:
        if "/" in raw_date:
            booking_date = datetime.strptime(raw_date, "%d/%m/%Y").date()
        else:
            booking_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Data invalida: '{raw_date}'. Use DD/MM/YYYY.")

    # Dia da semana (vazio = aula unica)
    raw_weekday = str(row.get(col["weekday"], "")).strip()
    weekday_num = WEEKDAY_MAP.get(raw_weekday)  # None se campo vazio

    return {
        "solicitation":  str(row.get(col["solicitation"], "Agendamento")).strip(),
        "lab":           str(row.get(col["lab"], "")).strip(),
        "period":        str(row.get(col["period"], "")).strip(),
        "num_students":  str(row.get(col["num_students"], "")).strip(),
        "professor":     str(row.get(col["professor"], "")).strip(),
        "email":         str(row.get(col["email"], "")).strip(),
        "discipline":    str(row.get(col["discipline"], "")).strip(),
        "date":          booking_date.isoformat(),
        "time_slot":     str(row.get(col["time_slot"], "")).strip(),
        "topic":         str(row.get(col["topic"], "")).strip(),
        "materials":     str(row.get(col["materials"], "")).strip(),
        "weekday":       weekday_num,
        "is_weekly":     1 if weekday_num is not None else 0,
        "parent_id":     None,
        # Campos auxiliares para templates
        "_date_obj":     booking_date,
    }


# ─── Montagem de contexto para templates ─────────────────────────────────────

def build_template_ctx(booking: dict) -> dict:
    ctx = {**booking}
    ctx["admin_name"]  = ADMIN_NAME
    ctx["admin_email"] = ADMIN_EMAIL
    ctx["min_days"]    = MIN_BUSINESS_DAYS_AHEAD

    # Linha de numero de alunos (so para Lab de Informatica)
    if booking.get("num_students"):
        ctx["num_students_line"] = f" Alunos       : {booking['num_students']}\n"
    else:
        ctx["num_students_line"] = ""

    # Linha de aula semanal
    if booking.get("is_weekly") and booking.get("weekday") is not None:
        day_names = {0:"Segundas",1:"Tercas",2:"Quartas",3:"Quintas",4:"Sextas"}
        ctx["weekly_line"] = f" Recorrencia  : Todas as {day_names.get(booking['weekday'],'')} a partir de {booking['date']}\n"
    else:
        ctx["weekly_line"] = ""

    return ctx


# ─── Processamento principal ──────────────────────────────────────────────────

def process_cancellation(booking: dict):
    professor = booking["professor"]
    email     = booking["email"]
    lab       = booking["lab"]
    date_str  = booking["date"]
    time_slot = booking["time_slot"]

    log.info(f"Cancelamento: {professor} -> {lab} em {date_str} {time_slot}")
    ctx = build_template_ctx(booking)

    cancelled = cancel_booking(lab, date_str, time_slot, professor)

    if cancelled:
        tpl = EMAIL_TEMPLATES["cancelled"]
        send_email(email, tpl["subject"].format(**ctx), tpl["body"].format(**ctx))
        send_email(
            ADMIN_EMAIL,
            f"[Cancelado] {lab} - {professor} - {date_str}",
            f"Reserva cancelada:\n\nProfessor: {professor} ({email})\nLaboratorio: {lab}\nData: {date_str} | {time_slot}\n",
        )
    else:
        tpl = EMAIL_TEMPLATES["cancel_not_found"]
        send_email(email, tpl["subject"].format(**ctx), tpl["body"].format(**ctx))
        send_email(
            ADMIN_EMAIL,
            f"[Cancelamento nao encontrado] {lab} - {professor} - {date_str}",
            f"Tentativa de cancelamento sem reserva correspondente:\n\nProfessor: {professor} ({email})\nLaboratorio: {lab}\nData: {date_str} | {time_slot}\n",
        )


def process_single_booking(booking: dict):
    """Processa um agendamento de data unica."""
    professor = booking["professor"]
    email     = booking["email"]
    lab       = booking["lab"]
    date_str  = booking["date"]
    time_slot = booking["time_slot"]
    date_obj  = booking["_date_obj"]

    ctx = build_template_ctx(booking)

    # Valida prazo minimo
    if not has_enough_lead_time(date_obj):
        log.warning(f"Prazo insuficiente: {lab} em {date_str}")
        tpl = EMAIL_TEMPLATES["deadline"]
        send_email(email, tpl["subject"].format(**ctx), tpl["body"].format(**ctx))
        send_email(
            ADMIN_EMAIL,
            f"[Prazo insuficiente] {lab} - {professor} - {date_str}",
            f"Solicitacao recusada por prazo:\n\nProfessor: {professor} ({email})\nLaboratorio: {lab}\nData: {date_str} | {time_slot}\n",
        )
        return

    # Valida conflito
    if is_conflicting(lab, date_str, time_slot):
        log.warning(f"Conflito detectado: {lab} em {date_str} {time_slot}")
        tpl = EMAIL_TEMPLATES["conflict"]
        send_email(email, tpl["subject"].format(**ctx), tpl["body"].format(**ctx))
        send_email(
            ADMIN_EMAIL,
            f"[Conflito] {lab} - {professor} - {date_str}",
            f"Solicitacao recusada por conflito:\n\nProfessor: {professor} ({email})\nLaboratorio: {lab}\nData: {date_str} | {time_slot}\n",
        )
        return

    # Salva e confirma
    save_booking(booking)
    log.info(f"Agendamento salvo: {lab} em {date_str} {time_slot}")
    tpl = EMAIL_TEMPLATES["confirmed"]
    send_email(email, tpl["subject"].format(**ctx), tpl["body"].format(**ctx))
    send_email(
        ADMIN_EMAIL,
        f"[Confirmado] {lab} - {professor} - {date_str}",
        f"Novo agendamento confirmado:\n\nProfessor: {professor} ({email})\nLaboratorio: {lab}\nData: {date_str} | {time_slot}\nTema: {booking['topic']}\nMateriais: {booking['materials']}\n",
    )


def process_weekly_booking(booking: dict):
    """Expande e processa todas as ocorrencias de uma aula semanal."""
    occurrences = expand_weekly_bookings(booking, weeks=16)
    confirmed_dates = []
    skipped_dates   = []

    for occ in occurrences:
        occ_date = date.fromisoformat(occ["date"])
        if not has_enough_lead_time(occ_date):
            skipped_dates.append(occ["date"])
            continue
        if is_conflicting(occ["lab"], occ["date"], occ["time_slot"]):
            skipped_dates.append(occ["date"])
            log.warning(f"Conflito semanal em {occ['date']}")
            continue
        save_booking(occ)
        confirmed_dates.append(occ["date"])

    professor = booking["professor"]
    email     = booking["email"]
    lab       = booking["lab"]
    ctx       = build_template_ctx(booking)

    # E-mail consolidado para o professor
    dates_str = "\n".join(f"  - {d}" for d in confirmed_dates) if confirmed_dates else "  (nenhuma)"
    skip_str  = "\n".join(f"  - {d}" for d in skipped_dates)   if skipped_dates  else "  (nenhuma)"

    body = (
        f"Prezado(a) Prof(a). {professor},\n\n"
        f"Seu agendamento semanal foi processado.\n\n"
        f"Laboratorio : {lab}\n"
        f"Horario     : {booking['time_slot']}\n"
        f"Disciplina  : {booking['discipline']}\n\n"
        f"DATAS CONFIRMADAS:\n{dates_str}\n\n"
        f"DATAS NAO CONFIRMADAS (conflito ou prazo):\n{skip_str}\n\n"
        f"Atenciosamente,\n{ADMIN_NAME}\nAnhanguera Educacional - Taubate\n{ADMIN_EMAIL}\n"
    )
    subject = f"[Semanal] Agendamento processado - {lab}"
    send_email(email, subject, body)
    send_email(ADMIN_EMAIL, f"[Semanal] {lab} - {professor}", body)
    log.info(f"Semanal processado: {len(confirmed_dates)} confirmados, {len(skipped_dates)} pulados.")


def process_row(row: dict):
    booking = parse_row(row)
    solicitation = booking["solicitation"].lower()

    if "cancelamento" in solicitation:
        process_cancellation(booking)
    elif booking["is_weekly"]:
        process_weekly_booking(booking)
    else:
        process_single_booking(booking)


# ─── Loop principal ───────────────────────────────────────────────────────────

def run_check():
    log.info("--- Verificando novas respostas ---")
    try:
        client = get_sheet_client()
        new_rows, last_row = fetch_new_responses(client)

        for i, row in enumerate(new_rows):
            try:
                process_row(row)
            except Exception as e:
                log.error(f"Erro ao processar linha {last_row + i + 1}: {e}")

        if new_rows:
            set_last_processed_row(last_row + len(new_rows))

    except Exception as e:
        log.error(f"Erro geral: {e}")


def main():
    init_db()
    log.info(f"Automacao iniciada. Intervalo: {CHECK_INTERVAL_MINUTES} minuto(s).")
    run_check()
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(run_check)
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()

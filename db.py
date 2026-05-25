"""
db.py - Camada de banco de dados SQLite
Suporta agendamentos unicos e semanais, cancelamentos e controle de linhas processadas.
"""

import sqlite3
import logging
from datetime import date, timedelta
from config import DB_PATH, WEEKDAY_MAP

log = logging.getLogger(__name__)


def _connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    """Cria as tabelas se ainda nao existirem."""
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS bookings (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                lab           TEXT    NOT NULL,
                period        TEXT,
                date          TEXT    NOT NULL,   -- ISO: YYYY-MM-DD
                time_slot     TEXT    NOT NULL,   -- texto livre, ex: "19h00 - 22h30"
                professor     TEXT    NOT NULL,
                email         TEXT    NOT NULL,
                discipline    TEXT,
                topic         TEXT,
                materials     TEXT,
                num_students  TEXT,
                is_weekly     INTEGER DEFAULT 0,  -- 1 se for aula semanal
                weekday       INTEGER,            -- 0=seg .. 4=sex, NULL se nao semanal
                parent_id     INTEGER,            -- ID do agendamento pai (para ocorrencias semanais)
                status        TEXT    DEFAULT 'active',  -- active | cancelled
                created_at    TEXT    DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS metadata (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            INSERT OR IGNORE INTO metadata (key, value)
            VALUES ('last_processed_row', '0');
        """)
    log.info("Banco de dados inicializado.")


def is_conflicting(lab: str, date_str: str, time_slot: str) -> bool:
    """
    Verifica se ja existe agendamento ativo para o mesmo laboratorio,
    data e horario (comparacao exata de time_slot).
    Para controle mais granular de sobreposicao de horario, ajuste conforme necessario.
    """
    query = """
        SELECT COUNT(*) FROM bookings
        WHERE lab      = ?
          AND date     = ?
          AND time_slot = ?
          AND status   = 'active'
    """
    with _connect() as conn:
        (count,) = conn.execute(query, (lab, date_str, time_slot)).fetchone()
    return count > 0


def save_booking(booking: dict) -> int:
    """Insere um agendamento e retorna o ID gerado."""
    query = """
        INSERT INTO bookings
            (lab, period, date, time_slot, professor, email, discipline,
             topic, materials, num_students, is_weekly, weekday, parent_id)
        VALUES
            (:lab, :period, :date, :time_slot, :professor, :email, :discipline,
             :topic, :materials, :num_students, :is_weekly, :weekday, :parent_id)
    """
    with _connect() as conn:
        cursor = conn.execute(query, booking)
        return cursor.lastrowid


def expand_weekly_bookings(booking: dict, weeks: int = 16) -> list:
    """
    A partir de um agendamento semanal (com weekday definido),
    gera todas as datas das proximas `weeks` semanas a partir da data inicial,
    filtrando apenas as que caem no dia da semana correto.
    Retorna lista de dicts prontos para save_booking.
    """
    target_weekday = booking["weekday"]
    start = date.fromisoformat(booking["date"])
    occurrences = []

    # Acha a primeira ocorrencia a partir da data inicial
    days_ahead = (target_weekday - start.weekday()) % 7
    first = start + timedelta(days=days_ahead)

    for i in range(weeks):
        occurrence_date = first + timedelta(weeks=i)
        entry = booking.copy()
        entry["date"] = occurrence_date.isoformat()
        entry["is_weekly"] = 1
        occurrences.append(entry)

    return occurrences


def cancel_booking(lab: str, date_str: str, time_slot: str, professor: str) -> bool:
    """
    Marca como cancelado o agendamento que corresponda aos parametros.
    Retorna True se encontrou e cancelou, False se nao encontrou.
    """
    query = """
        UPDATE bookings
        SET    status = 'cancelled'
        WHERE  lab       = ?
          AND  date      = ?
          AND  time_slot = ?
          AND  professor = ?
          AND  status    = 'active'
    """
    with _connect() as conn:
        cursor = conn.execute(query, (lab, date_str, time_slot, professor))
        return cursor.rowcount > 0


def get_last_processed_row() -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT value FROM metadata WHERE key = 'last_processed_row'"
        ).fetchone()
    return int(row[0]) if row else 0


def set_last_processed_row(n: int):
    with _connect() as conn:
        conn.execute(
            "UPDATE metadata SET value = ? WHERE key = 'last_processed_row'", (str(n),)
        )


def list_bookings(lab: str = None, date_str: str = None, professor: str = None):
    """Utilitario: lista agendamentos ativos com filtros opcionais."""
    query = "SELECT * FROM bookings WHERE status = 'active'"
    params = []
    if lab:
        query += " AND lab = ?"
        params.append(lab)
    if date_str:
        query += " AND date = ?"
        params.append(date_str)
    if professor:
        query += " AND professor LIKE ?"
        params.append(f"%{professor}%")
    query += " ORDER BY date, time_slot"
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return rows

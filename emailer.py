"""
emailer.py — Envio de e-mails via SMTP
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD

log = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str):
    """Envia um e-mail de texto simples."""
    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to, msg.as_string())
        log.info(f"E-mail enviado para {to} | Assunto: {subject}")
    except Exception as e:
        log.error(f"Falha ao enviar e-mail para {to}: {e}")
        raise

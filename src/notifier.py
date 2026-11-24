"""Alert notifications with 12-hour de-duplication.

Channels: console (always), Telegram, Email (SMTP).  Secrets come ONLY from
environment variables / .env - never hard-coded.  In simulation mode every
channel runs as a DRY-RUN so no real messages are ever sent.
"""
from __future__ import annotations
import os
import smtplib
from email.message import EmailMessage

import requests

from . import storage
from .config import DB_PATH
from .rules import SEV_ORDER

ICON = {"info": "ℹ️", "warn": "⚠️", "critical": "🚨"}


def format_message(city: str, a: dict) -> str:
    return (f"{ICON.get(a['severity'], '⚠️')} {a['severity'].upper()} | {city}\n"
            f"{a['label']}\n{a['message']}\nAdvice: {a['advice']}")


def send_telegram(text: str) -> bool:
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          data={"chat_id": chat, "text": text}, timeout=10)
        return r.ok
    except requests.RequestException:
        return False


def send_email(subject: str, body: str) -> bool:
    host, user, pwd, to = (os.getenv(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "ALERT_EMAIL_TO"))
    if not (host and user and pwd and to):
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", 587)), timeout=15) as s:
            s.starttls(); s.login(user, pwd); s.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError):
        return False


def dispatch(loc_id: int, city: str, alerts: list, dry_run: bool = True, min_severity: str = "warn",
             debounce_hours: int = 12, db=DB_PATH) -> list[dict]:
    """Send each NEW alert once per `debounce_hours`. Returns what was sent."""
    sent = []
    for a in alerts:
        a = a.to_dict() if hasattr(a, "to_dict") else a
        if SEV_ORDER[a["severity"]] < SEV_ORDER[min_severity]:
            continue
        if storage.recently_sent(loc_id, a["code"], debounce_hours, db):
            continue
        text = format_message(city, a)
        channels = ["console"]
        if not dry_run:
            if send_telegram(text): channels.append("telegram")
            if send_email(f"[{a['severity'].upper()}] {city}: {a['label']}", text): channels.append("email")
        else:
            channels = ["console(dry-run)"]
        storage.log_alert(loc_id, a, "+".join(channels), db)
        sent.append({**a, "channels": channels})
    return sent

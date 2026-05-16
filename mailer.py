"""Einfacher SMTP-Versand (z. B. für Lehrer-Benachrichtigungen).

Konfiguration per Umgebungsvariablen (z. B. in `.env` neben `app.py`, wird beim Start geladen):

SMTP_HOST       — z. B. smtp.gmail.com (leer = kein Versand)
SMTP_PORT       — Gmail: 587 + STARTTLS (Standard) oder 465 + SMTP_USE_SSL=1
SMTP_USER       — Login (leer = kein Login, nur für offene Relays)
SMTP_PASSWORD   — Passwort / App-Passwort
SMTP_FROM       — Absender-Adresse (falls leer: SMTP_USER)

SMTP_USE_SSL    — `1` / `true`: Verbindung mit SMTP_SSL (statt STARTTLS), typisch Port 465
SMTP_STARTTLS   — `0` / `false`: kein STARTTLS (nur sinnvoll ohne SMTP_USE_SSL)
SMTP_TIMEOUT    — Timeout in Sekunden (Standard 30)
"""

import os
import smtplib
from email.message import EmailMessage


def _env_bool(name, default=False):
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def smtp_configured():
    return bool(os.environ.get("SMTP_HOST", "").strip())


def smtp_status():
    host = os.environ.get("SMTP_HOST", "").strip()
    port = os.environ.get("SMTP_PORT", "587").strip() or "587"
    user = os.environ.get("SMTP_USER", "").strip()
    mail_from = os.environ.get("SMTP_FROM", "").strip() or user
    return {
        "configured": bool(host),
        "host": host,
        "port": port,
        "user_set": bool(user),
        "from": mail_from,
        "password_set": bool(os.environ.get("SMTP_PASSWORD", "").strip()),
        "use_ssl": _env_bool("SMTP_USE_SSL", False),
        "starttls": _env_bool("SMTP_STARTTLS", True),
    }


def send_smtp_mail(recipients, subject, body_plain):
    """
    recipients: Liste nicht-leerer E-Mail-Adressen
    Gibt (True, None) oder (False, reason) zurück.
    """
    if not recipients:
        return False, "no_recipients"
    host = os.environ.get("SMTP_HOST", "").strip()
    if not host:
        return False, "smtp_not_configured"
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
    except ValueError:
        port = 587
    try:
        timeout = float(os.environ.get("SMTP_TIMEOUT", "30"))
    except ValueError:
        timeout = 30.0
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    if host.lower() == "smtp.gmail.com":
        password = password.replace(" ", "")
    mail_from = os.environ.get("SMTP_FROM", "").strip() or user
    if not mail_from:
        return False, "smtp_no_from"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = recipients[0]
    if len(recipients) > 1:
        msg["Bcc"] = ", ".join(recipients[1:])
    msg.set_content(body_plain)

    use_ssl = _env_bool("SMTP_USE_SSL", False)
    want_starttls = _env_bool("SMTP_STARTTLS", True)

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=timeout) as smtp:
            smtp.ehlo()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        return True, None

    with smtplib.SMTP(host, port, timeout=timeout) as smtp:
        smtp.ehlo()
        if want_starttls:
            try:
                smtp.starttls()
                smtp.ehlo()
            except smtplib.SMTPException:
                pass
        if user:
            smtp.login(user, password)
        smtp.send_message(msg)
    return True, None

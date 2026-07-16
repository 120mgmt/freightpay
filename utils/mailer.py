# File: utils/mailer.py
# Production email service for FreightPay SaaS
# Supports SMTP (Gmail, SendGrid, Outlook, etc.)
# Hardened: SMTP_PORT empty/invalid will NOT crash boot

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os


def _smtp_port() -> int:
    raw = os.getenv("SMTP_PORT", "587")
    if raw is None:
        return 587
    raw = str(raw).strip()
    if raw == "":
        return 587
    try:
        v = int(raw)
        return v if v > 0 else 587
    except Exception:
        return 587


def _smtp_config():
    """
    Read at CALL time, not import time: settings saved through the admin
    portal (platform_settings -> os.environ) must apply without a restart.
    """
    host = (os.getenv("SMTP_HOST") or "").strip() or None
    user = (os.getenv("SMTP_USER") or "").strip() or None
    password = (os.getenv("SMTP_PASSWORD") or "").strip() or None
    from_email = (os.getenv("FROM_EMAIL") or "").strip() or (user or "")
    return host, _smtp_port(), user, password, from_email


def smtp_configured() -> bool:
    host, port, user, password, from_email = _smtp_config()
    return bool(host and port and user and password and from_email)


def send_email(to_email: str, subject: str, html_body: str):
    host, port, user, password, from_email = _smtp_config()
    if not all([host, port, user, password, from_email]):
        raise RuntimeError("SMTP settings not configured (set them in Admin -> Settings)")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    part = MIMEText(html_body, "html")
    msg.attach(part)

    try:
        server = smtplib.SMTP(host, port, timeout=20)
        server.starttls()
        server.login(user, password)
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        raise RuntimeError(f"Email send failed: {str(e)}")

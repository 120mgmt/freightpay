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


SMTP_HOST = (os.getenv("SMTP_HOST") or "").strip() or None
SMTP_PORT = _smtp_port()
SMTP_USER = (os.getenv("SMTP_USER") or "").strip() or None
SMTP_PASSWORD = (os.getenv("SMTP_PASSWORD") or "").strip() or None
FROM_EMAIL = (os.getenv("FROM_EMAIL") or "").strip() or (SMTP_USER or "")


def send_email(to_email: str, subject: str, html_body: str):
    if not all([SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, FROM_EMAIL]):
        raise RuntimeError("SMTP environment variables not fully configured")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email

    part = MIMEText(html_body, "html")
    msg.attach(part)

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        raise RuntimeError(f"Email send failed: {str(e)}")

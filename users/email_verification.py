# File: users/email_verification.py
# Purpose: Email verification (account activation)
# Status: Enterprise hardened
# Date: 2026-03-05

from __future__ import annotations

import os

from flask import Blueprint, current_app, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from db import db
from models.user import User
from utils.mailer import send_email


email_verify_bp = Blueprint("email_verify", __name__, url_prefix="/verify")


def _secret_key() -> str:
    key = (
        current_app.config.get("SECRET_KEY")
        or os.getenv("SECRET_KEY")
        or current_app.config.get("JWT_SECRET_KEY")
        or os.getenv("JWT_SECRET_KEY")
        or "ledgerhaul-dev-email-verification-key"
    )
    return str(key)


def _security_salt() -> str:
    return (
        current_app.config.get("SECURITY_SALT")
        or os.getenv("SECURITY_SALT")
        or "ledgerhaul-email-confirm"
    )


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret_key())


def generate_verification_token(email: str) -> str:
    return _serializer().dumps(email, salt=_security_salt())


def confirm_verification_token(token: str, expiration: int = 86400) -> str:
    return _serializer().loads(token, salt=_security_salt(), max_age=expiration)


@email_verify_bp.post("/send")
def send_verification():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({"error": "email_required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "user_not_found"}), 404

    if bool(getattr(user, "email_verified", False)):
        return jsonify({"status": "already_verified"}), 200

    token = generate_verification_token(user.email)

    frontend_url = (
        current_app.config.get("FRONTEND_URL")
        or os.getenv("FRONTEND_URL")
        or os.getenv("BASE_URL")
        or request.host_url.rstrip("/")
    )
    verify_url = f"{str(frontend_url).rstrip('/')}/verify-email?token={token}"

    first_name = getattr(user, "first_name", None) or "there"

    verify_button_html = (
        f'<a href="{verify_url}" '
        'style="padding:10px 14px;border:1px solid #111;'
        'border-radius:6px;text-decoration:none;">'
        'Verify Email'
        '</a>'
    )

    html_body = f"""
    <div style="font-family:Arial,sans-serif;">
        <p>Hi {first_name},</p>
        <p>Please verify your email to activate your LedgerHaul account.</p>
        <p>{verify_button_html}</p>
        <p>If you did not create this account, you can ignore this email.</p>
    </div>
    """

    send_email(
        to_email=user.email,
        subject="Verify your email",
        html_body=html_body,
    )

    return jsonify({"status": "verification_sent"}), 200


@email_verify_bp.post("/confirm")
def confirm_email():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()

    if not token:
        return jsonify({"error": "token_required"}), 400

    try:
        email = confirm_verification_token(token)
    except SignatureExpired:
        return jsonify({"error": "token_expired"}), 400
    except BadSignature:
        return jsonify({"error": "invalid_token"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "user_not_found"}), 404

    if bool(getattr(user, "email_verified", False)):
        return jsonify({"status": "already_verified"}), 200

    user.email_verified = True
    db.session.commit()

    return jsonify({"status": "email_verified"}), 200

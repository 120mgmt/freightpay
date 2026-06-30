# freightpay/users/routes.py
# Purpose: User auth + registration routes (deployment-ready)
# Status: Production-ready v6
# Date: 2026-06-30

from __future__ import annotations

import re

from flask import Blueprint, jsonify, request
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import User, Company
from utils.database import get_db
from utils.auth import require_auth, login_user, get_current_user

users_bp = Blueprint("users", __name__, url_prefix="/users")


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "company"


def _unique_slug(db: Session, base: str) -> str:
    slug = base[:140]
    if not db.execute(select(Company).where(Company.slug == slug)).scalar_one_or_none():
        return slug
    for i in range(2, 10000):
        candidate = f"{base[:136]}-{i}"
        if not db.execute(select(Company).where(Company.slug == candidate)).scalar_one_or_none():
            return candidate
    import uuid
    return str(uuid.uuid4())[:36]


@users_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "EMAIL_AND_PASSWORD_REQUIRED"}), 400

    db: Session = get_db()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    if not user or not user.is_active:
        return jsonify({"error": "INVALID_CREDENTIALS"}), 401

    if not user.check_password(password):
        return jsonify({"error": "INVALID_CREDENTIALS"}), 401

    if not bool(getattr(user, "email_verified", False)):
        return jsonify({"error": "EMAIL_NOT_VERIFIED"}), 403

    token = login_user(user=user)

    return jsonify(
        {
            "token": token,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
                "company_id": str(user.company_id),
            },
        }
    ), 200


@users_bp.post("/register")
def register():
    db: Session = get_db()
    data = request.get_json(silent=True) or {}

    company_name = (data.get("company_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()

    if not all([company_name, email, password, first_name, last_name]):
        return jsonify({"error": "MISSING_REQUIRED_FIELDS"}), 400

    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        return jsonify({"error": "EMAIL_ALREADY_EXISTS"}), 409

    slug = _unique_slug(db, _slugify(company_name))

    company = Company(name=company_name, slug=slug)
    db.add(company)
    db.flush()

    user = User(
        company_id=company.id,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role="admin",
        is_active=True,
        email_verified=False,
    )
    user.set_password(password)

    db.add(user)
    db.commit()

    # Send verification email — non-blocking, registration still succeeds if SMTP fails
    try:
        import os as _os
        from users.email_verification import generate_verification_token
        from utils.mailer import send_email
        _token = generate_verification_token(user.email)
        _base = _os.getenv("BASE_URL", "https://ledgerhaul.com").rstrip("/")
        _url = f"{_base}/verify-email?token={_token}"
        _html = (
            f"<div style='font-family:Arial,sans-serif;'>"
            f"<p>Hi {first_name},</p>"
            f"<p>Please verify your email to activate your LedgerHaul account.</p>"
            f"<p><a href='{_url}' style='display:inline-block;padding:10px 20px;"
            f"background:#36D394;color:#0E141B;border-radius:6px;"
            f"text-decoration:none;font-weight:600;'>Verify Email</a></p>"
            f"<p style='color:#888;font-size:13px;'>This link expires in 24 hours.</p>"
            f"</div>"
        )
        send_email(to_email=user.email, subject="Verify your LedgerHaul email", html_body=_html)
    except Exception:
        pass

    return jsonify(
        {
            "status": "created",
            "user_id": str(user.id),
            "company_id": str(company.id),
        }
    ), 201


@users_bp.get("/me")
@require_auth
def me():
    user = get_current_user()
    if not user:
        return jsonify({"error": "UNAUTHORIZED"}), 401
    return jsonify(
        {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "company_id": str(user.company_id),
            "is_active": user.is_active,
        }
    ), 200


@users_bp.patch("/me")
@require_auth
def update_me():
    user = get_current_user()
    if not user:
        return jsonify({"error": "UNAUTHORIZED"}), 401
    data = request.get_json(silent=True) or {}
    db: Session = get_db()
    if "first_name" in data and data["first_name"].strip():
        user.first_name = data["first_name"].strip()
    if "last_name" in data and data["last_name"].strip():
        user.last_name = data["last_name"].strip()
    if "email" in data and data["email"].strip():
        new_email = data["email"].strip().lower()
        if new_email != user.email:
            existing = db.execute(select(User).where(User.email == new_email)).scalar_one_or_none()
            if existing:
                return jsonify({"error": "EMAIL_ALREADY_EXISTS"}), 409
            user.email = new_email
    db.commit()
    return jsonify({"status": "updated"}), 200


@users_bp.post("/change-password")
@require_auth
def change_password():
    user = get_current_user()
    if not user:
        return jsonify({"error": "UNAUTHORIZED"}), 401
    data = request.get_json(silent=True) or {}
    current_pw = data.get("current_password") or ""
    new_pw = data.get("new_password") or ""
    if not current_pw or not new_pw:
        return jsonify({"error": "MISSING_FIELDS"}), 400
    if not user.check_password(current_pw):
        return jsonify({"error": "WRONG_PASSWORD"}), 403
    if len(new_pw) < 8:
        return jsonify({"error": "PASSWORD_TOO_SHORT"}), 400
    user.set_password(new_pw)
    db: Session = get_db()
    db.commit()
    return jsonify({"status": "password_changed"}), 200


@users_bp.post("/forgot-password")
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "EMAIL_REQUIRED"}), 400
    db: Session = get_db()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    # Always return 200 to avoid user enumeration
    if user and user.is_active:
        try:
            import os as _os
            from users.email_verification import generate_verification_token
            from utils.mailer import send_email
            _token = generate_verification_token(f"pwd-reset:{user.email}")
            _base = _os.getenv("BASE_URL", "https://ledgerhaul.com").rstrip("/")
            _url = f"{_base}/reset-password?token={_token}"
            _html = (
                f"<div style='font-family:Arial,sans-serif;'>"
                f"<p>Hi {user.first_name},</p>"
                f"<p>Click below to reset your LedgerHaul password. This link expires in 1 hour.</p>"
                f"<p><a href='{_url}' style='display:inline-block;padding:10px 20px;"
                f"background:#36D394;color:#0E141B;border-radius:6px;"
                f"text-decoration:none;font-weight:600;'>Reset Password</a></p>"
                f"<p style='color:#888;font-size:13px;'>If you didn't request this, ignore this email.</p>"
                f"</div>"
            )
            send_email(to_email=user.email, subject="Reset your LedgerHaul password", html_body=_html)
        except Exception:
            pass
    return jsonify({"status": "ok"}), 200


@users_bp.post("/reset-password")
def reset_password():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    new_pw = data.get("password") or ""
    if not token or not new_pw:
        return jsonify({"error": "MISSING_FIELDS"}), 400
    if len(new_pw) < 8:
        return jsonify({"error": "PASSWORD_TOO_SHORT"}), 400
    try:
        from users.email_verification import confirm_verification_token
        payload = confirm_verification_token(token, expiration=3600)
        if not payload.startswith("pwd-reset:"):
            return jsonify({"error": "INVALID_TOKEN"}), 400
        email = payload[len("pwd-reset:"):]
    except Exception:
        return jsonify({"error": "INVALID_OR_EXPIRED_TOKEN"}), 400
    db: Session = get_db()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user:
        return jsonify({"error": "USER_NOT_FOUND"}), 404
    user.set_password(new_pw)
    db.commit()
    return jsonify({"status": "password_reset"}), 200

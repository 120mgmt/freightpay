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

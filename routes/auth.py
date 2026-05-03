# File: routes/auth.py
# STATUS: LEGACY — NOT REGISTERED IN app.py
# The active auth blueprint is: routes/auth_routes.py
# This file is kept for reference only. Do NOT register this blueprint.
# If you need auth functionality, use routes/auth_routes.py
# Date: 2026-02-13

from __future__ import annotations

import os
from datetime import timedelta
from typing import Any, Dict, Tuple

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from sqlalchemy import select

from db import db
from models.user import User
from users.email_verification import generate_verification_token
from utils.mailer import send_email


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _json_error(message: str, status: int = 400, **extra: Any) -> Tuple[Any, int]:
    payload: Dict[str, Any] = {"error": message}
    payload.update(extra)
    return jsonify(payload), status


def _get_json() -> Dict[str, Any]:
    data = request.get_json(silent=True) or {}
    return data if isinstance(data, dict) else {}


def _token_expires() -> timedelta:
    # Default 24h; override with JWT_ACCESS_TOKEN_EXPIRES_HOURS
    try:
        hrs = int((os.getenv("JWT_ACCESS_TOKEN_EXPIRES_HOURS", "24") or "24").strip())
        hrs = max(1, min(hrs, 24 * 30))
    except Exception:
        hrs = 24
    return timedelta(hours=hrs)


def _normalize_email(v: Any) -> str:
    return str(v or "").strip().lower()


def _require_fields(data: Dict[str, Any], fields: list[str]) -> Tuple[bool, str]:
    for f in fields:
        if str(data.get(f) or "").strip() == "":
            return False, f
    return True, ""


def _require_company_id(data: Dict[str, Any]) -> int:
    raw = data.get("company_id") or request.headers.get("X-Company-Id") or request.args.get("company_id")
    try:
        cid = int(str(raw).strip())
        if cid <= 0:
            raise ValueError()
        return cid
    except Exception:
        raise ValueError("company_id must be a positive integer.")


def _safe_str(v: Any, *, max_len: int) -> str:
    s = str(v or "").strip()
    if len(s) > max_len:
        s = s[:max_len]
    return s


def _validate_password(pw: str) -> Tuple[bool, str]:
    # Keep rules simple, enforce minimum length at API boundary.
    pw = pw or ""
    if len(pw) < 10:
        return False, "password must be at least 10 characters"
    if len(pw) > 256:
        return False, "password is too long"
    return True, ""


def _normalize_role(v: Any) -> str:
    # Prevent arbitrary roles from being persisted.
    raw = str(v or "admin").strip().lower()
    allowed = {"admin", "member"}
    return raw if raw in allowed else "admin"


def _frontend_url() -> str:
    v = (os.getenv("FRONTEND_URL") or "").strip()
    return v.rstrip("/")


@auth_bp.get("/health")
def auth_health():
    return jsonify({"status": "ok"}), 200


@auth_bp.post("/register")
def register():
    """
    POST /auth/register
    Body:
      {
        "company_id": 1,
        "email": "you@domain.com",
        "password": "min 10 chars",
        "first_name": "Ashley",
        "last_name": "Ross",
        "accepted_tos": true,
        "accepted_privacy": true,
        "accepted_refund": true
      }

    HARD EMAIL VERIFICATION:
      - Creates user as email_verified=False
      - Sends verification email
      - DOES NOT issue access_token until verified
    """
    data = _get_json()

    ok, missing = _require_fields(
        data,
        ["email", "password", "first_name", "last_name"],
    )
    if not ok:
        return _json_error("missing_field", 400, field=missing)

    try:
        company_id = _require_company_id(data)
    except Exception as e:
        return _json_error("invalid_company_id", 400, detail=str(e))

    email = _normalize_email(data.get("email"))
    password = str(data.get("password") or "")

    # Basic size/format hardening
    if len(email) > 254:
        return _json_error("invalid_email", 400)
    pw_ok, pw_err = _validate_password(password)
    if not pw_ok:
        return _json_error("invalid_password", 400, detail=pw_err)

    accepted_tos = bool(data.get("accepted_tos", False))
    accepted_privacy = bool(data.get("accepted_privacy", False))
    accepted_refund = bool(data.get("accepted_refund", False))

    # Enforce legal acceptance for production readiness
    if not (accepted_tos and accepted_privacy and accepted_refund):
        return _json_error(
            "legal_acceptance_required",
            400,
            required=["accepted_tos", "accepted_privacy", "accepted_refund"],
        )

    existing = (
        db.session.execute(
            select(User).where(
                User.company_id == company_id,
                User.email == email,
            )
        ).scalar_one_or_none()
    )
    if existing:
        return _json_error("user_exists", 409)

    u = User(
        company_id=company_id,
        email=email,
        first_name=_safe_str(data.get("first_name"), max_len=80),
        last_name=_safe_str(data.get("last_name"), max_len=80),
        role=_normalize_role(data.get("role")),
        is_active=True,
    )

    # HARD: unverified until email confirmation
    u.email_verified = False

    try:
        u.set_password(password)
    except Exception as e:
        return _json_error("invalid_password", 400, detail=str(e))

    u.mark_legal_accepted(tos=True, privacy=True, refund=True)

    db.session.add(u)
    db.session.commit()

    # Send verification email (after commit so account exists even if SMTP fails)
    fe = _frontend_url()
    if not fe:
        return _json_error("frontend_url_not_configured", 500)

    token = generate_verification_token(u.email)
    verify_url = f"{fe}/verify-email?token={token}"

    html_body = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.5;">
      <p>Hi {u.first_name},</p>
      <p>Please verify your email to activate your LedgerHaul account.</p>
      <p>
        <a href="{verify_url}" style="display:inline-block;padding:10px 14px;border:1px solid #111;border-radius:6px;text-decoration:none;">
          Verify Email
        </a>
      </p>
      <p style="font-size:12px;color:#666;">If you did not create this account, you can ignore this email.</p>
    </div>
    """.strip()

    try:
        send_email(to_email=u.email, subject="Verify your email", html_body=html_body)
    except Exception as e:
        # Account created, but email did not send (operational issue)
        return _json_error("verification_email_failed", 500, detail=str(e), user=u.to_dict())

    return jsonify({"user": u.to_dict(), "verification_required": True}), 201


@auth_bp.post("/login")
def login():
    """
    POST /auth/login
    Body:
      {
        "company_id": 1,
        "email": "you@domain.com",
        "password": "..."
      }

    HARD EMAIL VERIFICATION:
      - Blocks login until email_verified=True
    """
    data = _get_json()
    ok, missing = _require_fields(data, ["email", "password"])
    if not ok:
        return _json_error("missing_field", 400, field=missing)

    try:
        company_id = _require_company_id(data)
    except Exception as e:
        return _json_error("invalid_company_id", 400, detail=str(e))

    email = _normalize_email(data.get("email"))
    password = str(data.get("password") or "")

    if len(email) > 254:
        return _json_error("invalid_credentials", 401)

    u = (
        db.session.execute(
            select(User).where(
                User.company_id == company_id,
                User.email == email,
            )
        ).scalar_one_or_none()
    )
    if not u or not u.check_password(password):
        return _json_error("invalid_credentials", 401)

    if not u.is_active:
        return _json_error("user_inactive", 403)

    # HARD GATE: email must be verified
    if not bool(getattr(u, "email_verified", False)):
        return _json_error("email_not_verified", 403)

    # Enforce legal acceptance at login (keeps you compliant)
    if not (u.accepted_tos and u.accepted_privacy and u.accepted_refund):
        return _json_error("legal_acceptance_required", 403)

    token = create_access_token(
        identity=str(u.id),
        additional_claims={
            "company_id": int(u.company_id),
            "role": u.role,
            "email": u.email,
        },
        expires_delta=_token_expires(),
    )

    return jsonify({"access_token": token, "user": u.to_dict()}), 200


@auth_bp.get("/me")
@jwt_required()
def me():
    """
    GET /auth/me
    Header:
      Authorization: Bearer <token>
    """
    user_id = get_jwt_identity()
    try:
        uid = int(str(user_id).strip())
    except Exception:
        return _json_error("invalid_token_identity", 401)

    claims = get_jwt() or {}
    try:
        token_company_id = int(str(claims.get("company_id") or "").strip())
    except Exception:
        return _json_error("invalid_token_company", 401)

    # Tenant-scope the lookup to prevent cross-tenant ID access.
    u = (
        db.session.execute(
            select(User).where(
                User.id == uid,
                User.company_id == token_company_id,
            )
        ).scalar_one_or_none()
    )
    if not u:
        return _json_error("user_not_found", 404)

    if not u.is_active:
        return _json_error("user_inactive", 403)

    # HARD GATE: verified accounts only
    if not bool(getattr(u, "email_verified", False)):
        return _json_error("email_not_verified", 403)

    # Keep compliance enforced for active sessions too.
    if not (u.accepted_tos and u.accepted_privacy and u.accepted_refund):
        return _json_error("legal_acceptance_required", 403)

    return jsonify({"user": u.to_dict()}), 200
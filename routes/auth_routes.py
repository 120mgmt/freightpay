# File: routes/auth_routes.py
# Purpose: Authentication + onboarding (register, login, legal acceptance) — TENANT-SAFE + ADMIN-ONLY USER CREATION
# Status: Production-ready (works with models/user.py + models/company.py + db.py + jwt_config.py)
# Date: 2026-02-22

from __future__ import annotations

import os
from datetime import timedelta
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, jsonify, request
import time
from collections import defaultdict
from threading import Lock

# ─── Brute-force / rate-limit state (in-memory, per-process) ───────────────
# For multi-process deploys, swap this for Redis-backed storage.
_login_attempts: dict = defaultdict(list)  # email -> [timestamp, ...]
_login_lock = Lock()
_LOCKOUT_MAX_ATTEMPTS = 5
_LOCKOUT_WINDOW_SECONDS = 300   # 5 minutes
_LOCKOUT_DURATION_SECONDS = 900 # 15 minutes


def _check_rate_limit(email: str) -> bool:
    """Returns True if login is allowed, False if locked out."""
    now = time.time()
    with _login_lock:
        attempts = _login_attempts[email]
        # Drop attempts outside the lockout window
        attempts = [t for t in attempts if now - t < _LOCKOUT_DURATION_SECONDS]
        _login_attempts[email] = attempts
        recent = [t for t in attempts if now - t < _LOCKOUT_WINDOW_SECONDS]
        return len(recent) < _LOCKOUT_MAX_ATTEMPTS


def _record_failed_attempt(email: str) -> None:
    with _login_lock:
        _login_attempts[email].append(time.time())


def _clear_attempts(email: str) -> None:
    with _login_lock:
        _login_attempts.pop(email, None)


from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    get_jwt,
    jwt_required,
)
from sqlalchemy import select

from db import db
from models.company import Company
from models.user import User
from models.refresh_token import RefreshToken
from users.email_verification import generate_verification_token
from utils.mailer import send_email

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# -------------------------------------------------
# Helpers
# -------------------------------------------------
_ALLOWED_ROLES = {"admin", "manager", "viewer"}

# Email verification modes:
# - "required": must verify, block login until verified, attempt email send
# - "best_effort": if email send fails or FRONTEND_URL missing, auto-verify so onboarding is not blocked
# - "off": skip sending + auto-verify (useful before SendGrid is configured)
_EMAIL_VERIFY_MODE = (os.getenv("EMAIL_VERIFICATION_MODE") or "best_effort").strip().lower()


def _json_error(msg: str, code: int = 400, **extra: Any) -> Tuple[Any, int]:
    payload: Dict[str, Any] = {"error": msg}
    payload.update(extra)
    return jsonify(payload), code


def _get_json() -> Dict[str, Any]:
    data = request.get_json(silent=True) or {}
    return data if isinstance(data, dict) else {}


def _token_expires() -> timedelta:
    # Default 12h; override with JWT_ACCESS_TOKEN_EXPIRES_HOURS
    try:
        hrs = int((os.getenv("JWT_ACCESS_TOKEN_EXPIRES_HOURS", "12") or "12").strip())
        hrs = max(1, min(hrs, 24 * 30))
    except Exception:
        hrs = 12
    return timedelta(hours=hrs)


def _safe_str(v: Any, *, max_len: int) -> str:
    s = str(v or "").strip()
    if len(s) > max_len:
        s = s[:max_len]
    return s


def _validate_password(pw: str) -> Optional[str]:
    """Server-side password strength enforcement — mirrors frontend requirements."""
    pw = pw or ""
    if len(pw) < 10:
        return "password too short (min 10 chars)"
    if len(pw) > 256:
        return "password too long"
    if not any(c.isupper() for c in pw):
        return "password must contain at least one uppercase letter"
    if not any(c.islower() for c in pw):
        return "password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in pw):
        return "password must contain at least one digit"
    special_chars = set('!@#$%^&*()_+-=[]{}|;:\'",./<>?')
    if not any(c in special_chars for c in pw):
        return "password must contain at least one special character"
    return None


def _slugify(name: str) -> str:
    s = (name or "").strip().lower()
    out = []
    last_dash = False
    for ch in s:
        if ch.isalnum():
            out.append(ch)
            last_dash = False
        else:
            if not last_dash:
                out.append("-")
                last_dash = True
    slug = "".join(out).strip("-")
    return slug or "company"


def _unique_slug(base: str) -> str:
    base = _slugify(base)
    slug = base
    n = 2
    while Company.query.filter_by(slug=slug).first():
        slug = f"{base}-{n}"
        n += 1
    return slug


def _normalize_role(role: Optional[str]) -> str:
    r = (role or "viewer").strip().lower()
    return r if r in _ALLOWED_ROLES else "viewer"


def _require_admin_identity() -> Dict[str, Any]:
    identity = get_jwt_identity() or {}
    if not isinstance(identity, dict):
        raise PermissionError("ADMIN_REQUIRED")
    role = (identity.get("role") or "").strip().lower()
    if role != "admin":
        raise PermissionError("ADMIN_REQUIRED")
    return identity


def _frontend_url() -> str:
    return (os.getenv("FRONTEND_URL") or "").strip().rstrip("/")


def _send_verify_email(*, user: User) -> Optional[str]:
    """
    Sends verification email. Returns None on success; returns error string on failure.
    """
    fe = _frontend_url()
    if not fe:
        return "FRONTEND_URL_NOT_CONFIGURED"

    token = generate_verification_token(user.email)
    verify_url = f"{fe}/verify-email?token={token}"

    html_body = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.5;">
      <p>Hi {user.first_name or ""},</p>
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
        send_email(to_email=user.email, subject="Verify your email", html_body=html_body)
        return None
    except Exception:
        return "VERIFICATION_EMAIL_FAILED"


def _company_picklist_for_email(email: str) -> list:
    """
    Returns a small list of companies this email belongs to (active users only).
    Used ONLY when the email exists in >1 company to force explicit choice.
    """
    stmt = (
        select(Company.id, Company.name, Company.slug)
        .join(User, User.company_id == Company.id)
        .where(User.email == email, User.is_active.is_(True), Company.is_active.is_(True))
        .distinct()
        .order_by(Company.id.asc())
    )
    rows = db.session.execute(stmt).all()
    return [{"id": int(r[0]), "name": str(r[1]), "slug": str(r[2])} for r in rows]


def _resolve_company_for_login(data: Dict[str, Any]) -> Tuple[Optional[Company], Optional[str], Optional[list]]:
    """
    Seamless login:
      - If company_id or company_slug provided: use it.
      - Else: infer company by email IF that email belongs to exactly 1 active company.
      - Else: require explicit company selection (returns list).
    Returns: (company_or_none, error_string_or_none, companies_list_or_none)
    """
    company_id = data.get("company_id")
    company_slug = (data.get("company_slug") or "").strip().lower()
    email = (data.get("email") or "").lower().strip()

    if company_id is not None and str(company_id).strip() != "":
        try:
            cid = int(company_id)
        except Exception:
            return None, "Invalid company_id", None
        company = Company.query.get(cid)
        if not company:
            return None, "Company not found", None
        return company, None, None

    if company_slug:
        company = Company.query.filter_by(slug=company_slug).first()
        if not company:
            return None, "Company not found", None
        return company, None, None

    # No company provided: infer by email
    if not email:
        return None, "email and password required", None

    companies = _company_picklist_for_email(email)
    if len(companies) == 0:
        # let normal credential error path handle it
        return None, "Invalid credentials", None

    if len(companies) == 1:
        only_id = int(companies[0]["id"])
        company = Company.query.get(only_id)
        if not company:
            return None, "Company not found", None
        return company, None, None

    # Multiple companies: force selection (enterprise-safe)
    return None, "COMPANY_SELECTION_REQUIRED", companies


def _should_require_email_verification() -> bool:
    return _EMAIL_VERIFY_MODE == "required"


def _should_auto_verify_on_send_failure() -> bool:
    return _EMAIL_VERIFY_MODE in {"best_effort", "off"}


# -------------------------------------------------
# REGISTER (creates company + first admin user ONLY)
# REQUIRE LEGAL ACCEPTANCE AT SIGNUP
# Email verification is configurable (see EMAIL_VERIFICATION_MODE)
# -------------------------------------------------
@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Creates a NEW company + the first ADMIN user.

    Body:
      {
        "company_name": "LedgerHaul LLC",
        "email": "...",
        "password": "...",
        "first_name": "...",
        "last_name": "...",
        "accepted_tos": true,
        "accepted_privacy": true,
        "accepted_refund": true
      }
    """
    data = _get_json()

    company_name = (data.get("company_name") or "").strip()
    email = (data.get("email") or "").lower().strip()
    password = data.get("password") or ""
    first_name = _safe_str(data.get("first_name"), max_len=80)
    last_name = _safe_str(data.get("last_name"), max_len=80)

    accepted_tos = data.get("accepted_tos") is True
    accepted_privacy = data.get("accepted_privacy") is True
    accepted_refund = data.get("accepted_refund") is True

    if not company_name:
        return _json_error("company_name required", 400)
    if not email or not password:
        return _json_error("email and password required", 400)
    if len(email) > 254:
        return _json_error("invalid email", 400)
    pw_err = _validate_password(password)
    if pw_err:
        return _json_error(pw_err, 400)

    # Force legal acceptance at signup to prevent broken onboarding
    if not (accepted_tos and accepted_privacy and accepted_refund):
        return _json_error("LEGAL_ACCEPTANCE_REQUIRED_AT_SIGNUP", 400)

    # Block duplicate email across the system (intentional baseline).
    if User.query.filter_by(email=email).first():
        return _json_error("User already exists", 409)

    slug = _unique_slug(company_name)
    company = Company(name=company_name, slug=slug, is_active=True)

    verification_email_sent = False
    verification_email_error: Optional[str] = None

    try:
        db.session.add(company)
        db.session.flush()  # get company.id without committing yet

        user = User(
            company_id=int(company.id),
            email=email,
            first_name=first_name or "",
            last_name=last_name or "",
            role="admin",
            is_active=True,
        )
        user.set_password(password)

        # Default verification behavior
        if _EMAIL_VERIFY_MODE == "off":
            user.email_verified = True
        else:
            user.email_verified = False

        # Always record legal acceptance now
        user.mark_legal_accepted(tos=True, privacy=True, refund=True)

        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return _json_error("Failed to register", 500, detail=str(e))

    # Verification email (post-commit so account exists even if email fails)
    if _EMAIL_VERIFY_MODE != "off":
        verification_email_error = _send_verify_email(user=user)
        verification_email_sent = verification_email_error is None

        # Best-effort mode: if email cannot be sent yet (no SendGrid), auto-verify to avoid blocking product build
        if verification_email_error and _should_auto_verify_on_send_failure():
            try:
                user.email_verified = True
                db.session.commit()
            except Exception:
                db.session.rollback()

    return jsonify(
        {
            "company": company.to_dict(),
            "user": user.to_dict(),
            "verification_required": _should_require_email_verification(),
            "verification_email_sent": verification_email_sent,
            "verification_email_error": verification_email_error,
        }
    ), 201


# -------------------------------------------------
# ADMIN: CREATE USER IN COMPANY (tenant-safe, admin-only)
# REQUIRE LEGAL ACCEPTANCE AND VERIFICATION POLICY
# -------------------------------------------------
@auth_bp.route("/companies/<int:company_id>/users", methods=["POST"])
@jwt_required()
def admin_create_user(company_id: int):
    """
    Admin-only: create an additional user for an existing company.

    Body:
      {
        "email": "...",
        "password": "...",
        "first_name": "...",
        "last_name": "...",
        "role": "manager|viewer|admin" (optional; defaults to viewer),
        "accepted_tos": true,
        "accepted_privacy": true,
        "accepted_refund": true
      }
    """
    try:
        identity = _require_admin_identity()
    except PermissionError:
        return _json_error("ADMIN_REQUIRED", 403)

    # Prevent cross-tenant admin misuse
    try:
        token_company_id = int(identity.get("company_id"))
    except Exception:
        return _json_error("Invalid token identity", 401)

    if token_company_id != int(company_id):
        return _json_error("FORBIDDEN_TENANT", 403)

    company = Company.query.get(int(company_id))
    if not company:
        return _json_error("Company not found", 404)
    if not company.is_active:
        return _json_error("Company inactive", 403)

    data = _get_json()
    email = (data.get("email") or "").lower().strip()
    password = data.get("password") or ""
    first_name = _safe_str(data.get("first_name"), max_len=80)
    last_name = _safe_str(data.get("last_name"), max_len=80)
    role = _normalize_role(data.get("role"))

    accepted_tos = data.get("accepted_tos") is True
    accepted_privacy = data.get("accepted_privacy") is True
    accepted_refund = data.get("accepted_refund") is True

    if not email or not password:
        return _json_error("email and password required", 400)
    if len(email) > 254:
        return _json_error("invalid email", 400)
    pw_err = _validate_password(password)
    if pw_err:
        return _json_error(pw_err, 400)

    if not (accepted_tos and accepted_privacy and accepted_refund):
        return _json_error("LEGAL_ACCEPTANCE_REQUIRED_AT_SIGNUP", 400)

    # Unique per company+email (your DB index enforces it too)
    if User.query.filter_by(company_id=int(company_id), email=email).first():
        return _json_error("User already exists in company", 409)

    verification_email_sent = False
    verification_email_error: Optional[str] = None

    try:
        user = User(
            company_id=int(company_id),
            email=email,
            first_name=first_name or "",
            last_name=last_name or "",
            role=role,
            is_active=True,
        )
        user.set_password(password)

        if _EMAIL_VERIFY_MODE == "off":
            user.email_verified = True
        else:
            user.email_verified = False

        user.mark_legal_accepted(tos=True, privacy=True, refund=True)

        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return _json_error("Failed to create user", 500, detail=str(e))

    if _EMAIL_VERIFY_MODE != "off":
        verification_email_error = _send_verify_email(user=user)
        verification_email_sent = verification_email_error is None

        if verification_email_error and _should_auto_verify_on_send_failure():
            try:
                user.email_verified = True
                db.session.commit()
            except Exception:
                db.session.rollback()

    return jsonify(
        {
            "company": company.to_dict(),
            "user": user.to_dict(),
            "verification_required": _should_require_email_verification(),
            "verification_email_sent": verification_email_sent,
            "verification_email_error": verification_email_error,
        }
    ), 201


# -------------------------------------------------
# LOGIN
# Seamless: email+password works when email belongs to exactly 1 company
# -------------------------------------------------
@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Seamless tenant login.

    Body:
      {
        "email": "...",
        "password": "...",
        "company_id": 1,              (optional)
        "company_slug": "..."         (optional)
      }
    """
    data = _get_json()

    email = (data.get("email") or "").lower().strip()
    password = data.get("password") or ""

    if not email or not password:
        return _json_error("email and password required", 400)
    if len(email) > 254:
        return _json_error("Invalid credentials", 401)

    company, company_err, companies = _resolve_company_for_login(data)
    if company is None:
        if company_err == "COMPANY_SELECTION_REQUIRED":
            # Return only company names — not IDs — to prevent org data disclosure
            safe_companies = [
                {"name": c.get("name", ""), "slug": c.get("slug", "")}
                for c in (companies or [])
            ] if companies else []
            return _json_error("COMPANY_SELECTION_REQUIRED", 409, companies=safe_companies)
        # normalize invalid email case to generic auth error
        if company_err == "Invalid credentials":
            return _json_error("Invalid credentials", 401)
        return _json_error(company_err or "company resolution failed", 400)

    if not company.is_active:
        return _json_error("Company inactive", 403)

    # ── Rate limit / lockout check ─────────────────────────────────────────
    if not _check_rate_limit(email):
        return _json_error("Too many failed login attempts. Try again in 15 minutes.", 429)

    user = User.query.filter_by(company_id=int(company.id), email=email, is_active=True).first()
    if not user or not user.check_password(password):
        _record_failed_attempt(email)
        return _json_error("Invalid credentials", 401)

    _clear_attempts(email)  # successful auth resets counter

    # Email verification policy
    if _should_require_email_verification() and not bool(getattr(user, "email_verified", False)):
        return _json_error("EMAIL_NOT_VERIFIED", 403)

    # Legal acceptance gate (should be satisfied at signup now)
    if not (user.accepted_tos and user.accepted_privacy and user.accepted_refund):
        return _json_error("LEGAL_ACCEPTANCE_REQUIRED", 403)

    identity = {
        "user_id": int(user.id),
        "company_id": int(user.company_id),
        "role": user.role,
        "email": user.email,
    }

    access_token = create_access_token(identity=identity, expires_delta=_token_expires())
    refresh_token = create_refresh_token(identity=identity)

    # Persist refresh token jti for rotation/revocation
    try:
        from flask_jwt_extended import decode_token
        decoded = decode_token(refresh_token)
        jti = decoded.get("jti")
        if jti:
            rt = RefreshToken(user_id=int(user.id), jti=jti, token_type="refresh")
            db.session.add(rt)
            db.session.commit()
    except Exception:
        pass  # Non-fatal: token still issued

    return jsonify({"access_token": access_token, "refresh_token": refresh_token, "user": user.to_dict(), "company": company.to_dict()}), 200


# -------------------------------------------------
# ACCEPT LEGAL (TOS / PRIVACY / REFUND)
# -------------------------------------------------
@auth_bp.route("/legal/accept", methods=["POST"])
@jwt_required()
def accept_legal():
    """
    Body:
      { "accepted_tos": true, "accepted_privacy": true, "accepted_refund": true }
    """
    identity = get_jwt_identity() or {}
    if not isinstance(identity, dict):
        return _json_error("Invalid token identity", 401)

    try:
        user_id = int(identity.get("user_id"))
        company_id = int(identity.get("company_id"))
    except Exception:
        return _json_error("Invalid token identity", 401)

    data = _get_json()
    accepted_tos = data.get("accepted_tos") is True
    accepted_privacy = data.get("accepted_privacy") is True
    accepted_refund = data.get("accepted_refund") is True

    user = User.query.filter_by(id=int(user_id), company_id=int(company_id)).first()
    if not user:
        return _json_error("User not found", 404)
    if not user.is_active:
        return _json_error("User inactive", 403)

    user.mark_legal_accepted(tos=accepted_tos, privacy=accepted_privacy, refund=accepted_refund)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return _json_error("Failed to accept legal", 500, detail=str(e))

    return jsonify({"user": user.to_dict()}), 200


# -------------------------------------------------
# REFRESH TOKEN — rotate on use
# -------------------------------------------------
@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh_token():
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    Old refresh token is revoked (rotation).
    """
    identity = get_jwt_identity()
    jti = get_jwt().get("jti")

    # Revoke old refresh token
    if jti:
        old_rt = RefreshToken.query.filter_by(jti=jti, revoked=False).first()
        if not old_rt:
            return _json_error("Refresh token invalid or already revoked", 401)
        old_rt.revoked = True
        db.session.commit()

    # Issue new pair
    new_access = create_access_token(identity=identity, expires_delta=_token_expires())
    new_refresh = create_refresh_token(identity=identity)

    try:
        from flask_jwt_extended import decode_token
        decoded = decode_token(new_refresh)
        new_jti = decoded.get("jti")
        if new_jti:
            rt = RefreshToken(
                user_id=int(identity.get("user_id")),
                jti=new_jti,
                token_type="refresh",
            )
            db.session.add(rt)
            db.session.commit()
    except Exception:
        pass

    return jsonify({"access_token": new_access, "refresh_token": new_refresh}), 200


# -------------------------------------------------
# LOGOUT — revoke refresh token
# -------------------------------------------------
@auth_bp.route("/logout", methods=["POST"])
@jwt_required(refresh=True)
def logout():
    """Revoke refresh token on logout."""
    jti = get_jwt().get("jti")
    if jti:
        rt = RefreshToken.query.filter_by(jti=jti, revoked=False).first()
        if rt:
            rt.revoked = True
            db.session.commit()
    return jsonify({"message": "Logged out successfully"}), 200

# File: routes/admin_portal.py
# Purpose: Platform-owner admin portal API (cross-tenant visibility + controls)
# Access: ONLY users whose email is listed in PLATFORM_ADMIN_EMAILS (comma-separated env var).
#         This is intentionally separate from the per-company "admin" role, which every
#         company owner has for their own tenant.
# Import expectation (in app.py):
#     from routes.admin_portal import admin_portal_bp
# Date: 2026-07-15

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select, text

from db import db
from models.company import Company
from models.user import User
from utils.auth import get_current_user

T = TypeVar("T")

admin_portal_bp = Blueprint("admin_portal", __name__, url_prefix="/api/admin")

ALLOWED_ROLES = {"admin", "manager", "viewer"}


# ------------------------------------------------------------------
# Access control
# ------------------------------------------------------------------
def _platform_admin_emails() -> set[str]:
    raw = os.getenv("PLATFORM_ADMIN_EMAILS", "") or ""
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_platform_admin_email(email: Optional[str]) -> bool:
    if not email:
        return False
    return email.strip().lower() in _platform_admin_emails()


def platform_admin_required(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        from flask_jwt_extended import verify_jwt_in_request

        try:
            verify_jwt_in_request()
        except Exception:
            return jsonify({"error": "UNAUTHORIZED"}), 401

        user = get_current_user()
        if not user or not user.is_active:
            return jsonify({"error": "UNAUTHORIZED"}), 401
        if not is_platform_admin_email(user.email):
            return jsonify({"error": "PLATFORM_ADMIN_ONLY"}), 403

        request.platform_admin = user  # type: ignore[attr-defined]
        return fn(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _pagination() -> tuple[int, int]:
    try:
        page = max(1, int(request.args.get("page", 1)))
    except Exception:
        page = 1
    try:
        per_page = min(100, max(1, int(request.args.get("per_page", 25))))
    except Exception:
        per_page = 25
    return page, per_page


def _user_row(u: User, company_name: Optional[str] = None) -> Dict[str, Any]:
    return {
        "id": u.id,
        "email": u.email,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "role": u.role,
        "is_active": bool(u.is_active),
        "email_verified": bool(u.email_verified),
        "company_id": u.company_id,
        "company_name": company_name,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "is_platform_admin": is_platform_admin_email(u.email),
    }


def _table_exists(name: str) -> bool:
    try:
        return db.session.execute(
            text("SELECT to_regclass(:n)"), {"n": name}
        ).scalar() is not None
    except Exception:
        db.session.rollback()
        return False


# ------------------------------------------------------------------
# Overview
# ------------------------------------------------------------------
@admin_portal_bp.get("/overview")
@platform_admin_required
def overview():
    s = db.session
    now = datetime.now(timezone.utc)

    companies_total = s.execute(select(func.count(Company.id))).scalar() or 0
    companies_active = s.execute(
        select(func.count(Company.id)).where(Company.is_active.is_(True))
    ).scalar() or 0
    companies_with_stripe = s.execute(
        select(func.count(Company.id)).where(Company.stripe_customer_id.isnot(None))
    ).scalar() or 0

    users_total = s.execute(select(func.count(User.id))).scalar() or 0
    users_active = s.execute(
        select(func.count(User.id)).where(User.is_active.is_(True))
    ).scalar() or 0
    users_verified = s.execute(
        select(func.count(User.id)).where(User.email_verified.is_(True))
    ).scalar() or 0
    users_last_7d = s.execute(
        select(func.count(User.id)).where(User.created_at >= now - timedelta(days=7))
    ).scalar() or 0
    users_last_30d = s.execute(
        select(func.count(User.id)).where(User.created_at >= now - timedelta(days=30))
    ).scalar() or 0

    payroll_runs_total = 0
    payroll_runs_finalized = 0
    if _table_exists("payroll_runs"):
        payroll_runs_total = s.execute(
            text("SELECT COUNT(*) FROM payroll_runs")
        ).scalar() or 0
        payroll_runs_finalized = s.execute(
            text("SELECT COUNT(*) FROM payroll_runs WHERE finalized = true")
        ).scalar() or 0

    recent = s.execute(
        select(User, Company.name)
        .join(Company, Company.id == User.company_id)
        .order_by(User.created_at.desc())
        .limit(8)
    ).all()

    return jsonify(
        {
            "companies": {
                "total": int(companies_total),
                "active": int(companies_active),
                "with_stripe_customer": int(companies_with_stripe),
            },
            "users": {
                "total": int(users_total),
                "active": int(users_active),
                "verified": int(users_verified),
                "new_last_7d": int(users_last_7d),
                "new_last_30d": int(users_last_30d),
            },
            "payroll_runs": {
                "total": int(payroll_runs_total),
                "finalized": int(payroll_runs_finalized),
            },
            "recent_signups": [_user_row(u, cname) for (u, cname) in recent],
        }
    ), 200


# ------------------------------------------------------------------
# Companies
# ------------------------------------------------------------------
@admin_portal_bp.get("/companies")
@platform_admin_required
def list_companies():
    s = db.session
    page, per_page = _pagination()
    q = (request.args.get("q") or "").strip()

    base = select(Company)
    count_q = select(func.count(Company.id))
    if q:
        like = f"%{q}%"
        base = base.where(Company.name.ilike(like) | Company.slug.ilike(like))
        count_q = count_q.where(Company.name.ilike(like) | Company.slug.ilike(like))

    total = s.execute(count_q).scalar() or 0
    companies = s.execute(
        base.order_by(Company.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).scalars().all()

    ids = [c.id for c in companies]
    user_counts: Dict[int, int] = {}
    if ids:
        rows = s.execute(
            select(User.company_id, func.count(User.id))
            .where(User.company_id.in_(ids))
            .group_by(User.company_id)
        ).all()
        user_counts = {cid: int(n) for cid, n in rows}

    return jsonify(
        {
            "total": int(total),
            "page": page,
            "per_page": per_page,
            "companies": [
                {**c.to_dict(), "user_count": user_counts.get(c.id, 0)}
                for c in companies
            ],
        }
    ), 200


@admin_portal_bp.get("/companies/<int:company_id>")
@platform_admin_required
def company_detail(company_id: int):
    s = db.session
    company = s.get(Company, company_id)
    if not company:
        return jsonify({"error": "COMPANY_NOT_FOUND"}), 404

    users = s.execute(
        select(User).where(User.company_id == company_id).order_by(User.created_at)
    ).scalars().all()

    payroll_runs: List[Dict[str, Any]] = []
    if _table_exists("payroll_runs"):
        rows = s.execute(
            text(
                "SELECT run_id, created_at, status, finalized "
                "FROM payroll_runs WHERE company_id = :cid "
                "ORDER BY created_at DESC LIMIT 10"
            ),
            {"cid": company_id},
        ).all()
        payroll_runs = [
            {
                "run_id": r[0],
                "created_at": int(r[1]) if r[1] is not None else None,
                "status": r[2],
                "finalized": bool(r[3]),
            }
            for r in rows
        ]

    subscription: Dict[str, Any] = {"status": "none", "plan": None}
    if company.stripe_customer_id:
        subscription = _subscription_for_customer(company.stripe_customer_id)

    return jsonify(
        {
            "company": company.to_dict(),
            "users": [_user_row(u, company.name) for u in users],
            "payroll_runs": payroll_runs,
            "subscription": subscription,
        }
    ), 200


@admin_portal_bp.patch("/companies/<int:company_id>")
@platform_admin_required
def patch_company(company_id: int):
    s = db.session
    company = s.get(Company, company_id)
    if not company:
        return jsonify({"error": "COMPANY_NOT_FOUND"}), 404

    data = request.get_json(silent=True) or {}
    if "is_active" in data:
        company.is_active = bool(data["is_active"])
    if "name" in data and str(data["name"]).strip():
        company.name = str(data["name"]).strip()

    s.commit()
    return jsonify({"status": "updated", "company": company.to_dict()}), 200


# ------------------------------------------------------------------
# Users
# ------------------------------------------------------------------
@admin_portal_bp.get("/users")
@platform_admin_required
def list_users():
    s = db.session
    page, per_page = _pagination()
    q = (request.args.get("q") or "").strip()

    base = select(User, Company.name).join(Company, Company.id == User.company_id)
    count_q = select(func.count(User.id))
    if q:
        like = f"%{q}%"
        cond = (
            User.email.ilike(like)
            | User.first_name.ilike(like)
            | User.last_name.ilike(like)
        )
        base = base.where(cond)
        count_q = count_q.where(cond)

    total = s.execute(count_q).scalar() or 0
    rows = s.execute(
        base.order_by(User.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()

    return jsonify(
        {
            "total": int(total),
            "page": page,
            "per_page": per_page,
            "users": [_user_row(u, cname) for (u, cname) in rows],
        }
    ), 200


@admin_portal_bp.patch("/users/<int:user_id>")
@platform_admin_required
def patch_user(user_id: int):
    s = db.session
    user = s.get(User, user_id)
    if not user:
        return jsonify({"error": "USER_NOT_FOUND"}), 404

    me: User = request.platform_admin  # type: ignore[attr-defined]
    data = request.get_json(silent=True) or {}

    if "is_active" in data:
        new_active = bool(data["is_active"])
        if user.id == me.id and not new_active:
            return jsonify({"error": "CANNOT_DEACTIVATE_SELF"}), 400
        user.is_active = new_active

    if "role" in data:
        role = str(data["role"]).strip().lower()
        if role not in ALLOWED_ROLES:
            return jsonify({"error": "INVALID_ROLE", "allowed": sorted(ALLOWED_ROLES)}), 400
        user.role = role

    if "email_verified" in data:
        user.email_verified = bool(data["email_verified"])

    s.commit()
    return jsonify({"status": "updated", "user": _user_row(user)}), 200


@admin_portal_bp.post("/users/<int:user_id>/reset-link")
@platform_admin_required
def user_reset_link(user_id: int):
    """
    Generates a one-hour password-reset link for the user (same token flow
    as the self-service forgot-password email) so the platform admin can
    hand it to a locked-out customer directly.
    """
    s = db.session
    user = s.get(User, user_id)
    if not user:
        return jsonify({"error": "USER_NOT_FOUND"}), 404

    from users.email_verification import generate_verification_token

    token = generate_verification_token(f"pwd-reset:{user.email}")
    base = os.getenv("BASE_URL", "https://ledgerhaul.com").rstrip("/")
    return jsonify(
        {
            "reset_url": f"{base}/reset-password?token={token}",
            "expires_in_seconds": 3600,
        }
    ), 200


# ------------------------------------------------------------------
# Payroll runs (cross-tenant)
# ------------------------------------------------------------------
@admin_portal_bp.get("/payroll-runs")
@platform_admin_required
def list_payroll_runs():
    if not _table_exists("payroll_runs"):
        return jsonify({"total": 0, "runs": []}), 200

    s = db.session
    page, per_page = _pagination()

    total = s.execute(text("SELECT COUNT(*) FROM payroll_runs")).scalar() or 0
    rows = s.execute(
        text(
            "SELECT pr.run_id, pr.company_id, c.name, pr.created_at, pr.status, "
            "       pr.finalized, pr.results_json "
            "FROM payroll_runs pr "
            "LEFT JOIN companies c ON c.id = pr.company_id "
            "ORDER BY pr.created_at DESC "
            "LIMIT :lim OFFSET :off"
        ),
        {"lim": per_page, "off": (page - 1) * per_page},
    ).all()

    runs = []
    for r in rows:
        total_net: Optional[float] = None
        try:
            results = json.loads(r[6]) if r[6] else None
            if isinstance(results, dict):
                totals = results.get("totals") or {}
                if isinstance(totals, dict) and totals.get("net") is not None:
                    total_net = float(totals["net"])
        except Exception:
            pass
        runs.append(
            {
                "run_id": r[0],
                "company_id": r[1],
                "company_name": r[2],
                "created_at": int(r[3]) if r[3] is not None else None,
                "status": r[4],
                "finalized": bool(r[5]),
                "total_net": total_net,
            }
        )

    return jsonify(
        {"total": int(total), "page": page, "per_page": per_page, "runs": runs}
    ), 200


# ------------------------------------------------------------------
# Subscriptions (Stripe, best-effort)
# ------------------------------------------------------------------
def _subscription_for_customer(customer_id: str) -> Dict[str, Any]:
    try:
        from billing.checkout import _plan_key_for_price, _stripe_client

        stripe = _stripe_client()
        subs = stripe.Subscription.list(customer=customer_id, status="all", limit=5)
        items = subs.get("data") or []
        rank = {"active": 0, "trialing": 1, "past_due": 2, "unpaid": 3, "canceled": 4}
        items.sort(key=lambda x: rank.get(x.get("status"), 9))
        if not items:
            return {"status": "none", "plan": None}

        sub = items[0]
        plan_key = None
        for li in (sub.get("items", {}).get("data") or []):
            plan_key = _plan_key_for_price((li.get("price") or {}).get("id") or "")
            if plan_key:
                break
        period_end = sub.get("current_period_end")
        return {
            "status": sub.get("status") or "none",
            "plan": plan_key,
            "current_period_end": (
                datetime.fromtimestamp(int(period_end), tz=timezone.utc).isoformat()
                if period_end
                else None
            ),
            "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
        }
    except Exception as e:
        return {"status": "error", "plan": None, "detail": str(e)}


@admin_portal_bp.get("/subscriptions")
@platform_admin_required
def list_subscriptions():
    """
    Subscription status for every company that has a Stripe customer.
    Capped at 25 companies per call (one Stripe API call each).
    """
    s = db.session
    companies = s.execute(
        select(Company)
        .where(Company.stripe_customer_id.isnot(None))
        .order_by(Company.created_at.desc())
        .limit(25)
    ).scalars().all()

    started = time.time()
    out = []
    for c in companies:
        if time.time() - started > 20:  # keep the request well under gunicorn timeout
            out.append({"company_id": c.id, "company_name": c.name, "status": "skipped_timeout"})
            continue
        sub = _subscription_for_customer(c.stripe_customer_id)
        out.append(
            {
                "company_id": c.id,
                "company_name": c.name,
                "stripe_customer_id": c.stripe_customer_id,
                **sub,
            }
        )

    return jsonify({"subscriptions": out, "count": len(out)}), 200


if __name__ == "__main__":
    assert admin_portal_bp.name == "admin_portal"
    print("routes/admin_portal.py OK")

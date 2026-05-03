# File: utils/subscription_guard.py
# Purpose: Subscription gate enforcement (prevents paid-feature access without active subscription)
# Status: Production-ready (fail-safe, no hard dependency on specific company billing fields)
# Date: 2026-02-16

from __future__ import annotations

from typing import Any, Optional, Tuple

import logging
from flask import jsonify, request

_log = logging.getLogger("ledgerhaul.subscription_guard")

# NOTE:
# This guard is designed to NOT crash if billing fields evolve.
# It enforces subscription only when it can reliably determine subscription status.


def _json_error(code: str, message: str, http_status: int, **extra: Any) -> Tuple[Any, int]:
    payload = {"error": code, "message": message}
    payload.update(extra)
    return jsonify(payload), http_status


def _is_public_path(path: str) -> bool:
    # Always-allowed routes (do not gate)
    if (
        path == "/"
        or path == "/health"
        or path.startswith("/static/")
        or path.startswith("/legal/")
        or path.startswith("/auth/")           # login/register/verify flows
        or path.startswith("/companies")       # onboarding / tenant creation
        or path.startswith("/billing/webhooks")  # Stripe webhooks must always pass
        or path.startswith("/webhook")
    ):
        return True
    return False


def _get_identity() -> Optional[dict]:
    """
    Returns JWT identity dict if JWT is configured and token is present.
    Fails safely (returns None) if JWT not configured or no token.
    """
    try:
        from flask_jwt_extended import get_jwt_identity  # type: ignore
    except Exception:
        return None

    try:
        ident = get_jwt_identity()
        return ident if isinstance(ident, dict) else None
    except Exception:
        return None


def _resolve_company(company_id: int):
    try:
        from models.company import Company  # local import to avoid circulars
    except Exception:
        return None

    try:
        return Company.query.get(int(company_id))
    except Exception:
        return None


def _company_subscription_is_active(company: Any) -> Optional[bool]:
    """
    Tries common patterns without assuming a single schema.
    Returns:
      - True / False if determinable
      - None if not determinable (guard will fail-open instead of crashing)
    """
    # Boolean flags
    for attr in ("subscription_active", "is_subscribed", "is_subscription_active"):
        if hasattr(company, attr):
            try:
                return bool(getattr(company, attr))
            except Exception:
                _log.warning("Could not read boolean attr %s from company", attr)
                return None

    # Status strings
    for attr in ("subscription_status", "stripe_subscription_status", "billing_status"):
        if hasattr(company, attr):
            try:
                v = (getattr(company, attr) or "").strip().lower()
                if not v:
                    return False
                return v in {"active", "trialing", "trial", "paid"}
            except Exception:
                _log.warning("Could not read status attr %s from company", attr)
                return None

    # If you store subscription_id only, we cannot infer active vs canceled safely
    # without calling Stripe or storing status locally.
    if hasattr(company, "stripe_subscription_id"):
        try:
            sid = (getattr(company, "stripe_subscription_id") or "").strip()
            if sid:
                # Determinability is unknown without local status; return None (fail-open).
                return None
            return False
        except Exception:
            _log.warning("Could not read stripe_subscription_id from company")
            return None

    return None


def enforce_subscription_active():
    """
    Use via @app.before_request.

    Behavior:
    - Always allows public + onboarding + webhook + legal + auth routes.
    - If request is unauthenticated, allows (public browsing / marketing usage).
    - If authenticated:
        - Blocks if company missing/inactive
        - Blocks if subscription is determinably inactive
        - If subscription cannot be determined from current schema, fails open (does not break prod)
    """
    path = (request.path or "").strip()

    if request.method == "OPTIONS" or _is_public_path(path):
        return None

    identity = _get_identity()
    if not identity:
        return None

    company_id = identity.get("company_id")
    if company_id is None or str(company_id).strip() == "":
        # If authenticated but missing tenant context, treat as invalid token identity.
        return _json_error("INVALID_IDENTITY", "Missing company context in token.", 401)

    try:
        cid = int(company_id)
    except Exception:
        return _json_error("INVALID_IDENTITY", "Invalid company_id in token.", 401)

    company = _resolve_company(cid)
    if not company:
        return _json_error("COMPANY_NOT_FOUND", "Company not found.", 404)

    # Company active gate (common)
    if hasattr(company, "is_active"):
        try:
            if not bool(company.is_active):
                return _json_error("COMPANY_INACTIVE", "Company is inactive.", 403)
        except Exception:
            _log.warning("Could not read is_active from company id=%s", company_id)

    active = _company_subscription_is_active(company)

    # Determinable and inactive => BLOCK
    if active is False:
        return _json_error(
            "SUBSCRIPTION_REQUIRED",
            "Active subscription required to access this feature.",
            402,
            checkout_hint="/billing/checkout-link",
            portal_hint="/billing/portal/session",
        )

    # active True or unknown => allow
    return None


__all__ = ["enforce_subscription_active"]
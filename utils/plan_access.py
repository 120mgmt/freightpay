# File: utils/plan_access.py
# Purpose: Plan-aware feature gating for the three real packages
#          (payroll_only / bookkeeping_only / combo).
# Why: the legacy entitlement tiers (starter/pro/enterprise) grant payroll to
#      everyone and know nothing about "bookkeeping", so they cannot enforce
#      the actual product packages. This resolves a company's real plan from
#      its manual override or its live Stripe subscription and gates by
#      capability.
# Date: 2026-07-18

from __future__ import annotations

import os
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from flask import jsonify, request

from db import db

F = TypeVar("F", bound=Callable[..., Any])

# capability -> the packages that include it
CAPABILITY_PLANS = {
    "payroll": {"payroll_only", "combo"},
    "bookkeeping": {"bookkeeping_only", "combo"},
}

CAPABILITY_PLANS_ALL = {"payroll_only", "bookkeeping_only", "combo"}

PLAN_LABEL = {
    "payroll_only": "Payroll Only",
    "bookkeeping_only": "Bookkeeping Only",
    "combo": "Combo",
}


def _truthy(v: Optional[str]) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _gating_enforced() -> bool:
    """Gating is on unless subscription enforcement is disabled or bypassed."""
    if _truthy(os.getenv("SUBSCRIPTION_BYPASS", "0")):
        return False
    try:
        from billing.entitlement import subscription_required_enabled

        return bool(subscription_required_enabled())
    except Exception:
        # Default to enforcing — the product is subscription-only.
        return True


def _extract_company_id() -> Optional[int]:
    cid = request.headers.get("X-Company-Id") or request.args.get("company_id")
    if not cid:
        data = request.get_json(silent=True) or {}
        if isinstance(data, dict):
            cid = data.get("company_id")
    if not cid:
        # Fall back to JWT identity.
        try:
            from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

            verify_jwt_in_request(optional=True)
            ident = get_jwt_identity()
            if isinstance(ident, dict):
                cid = ident.get("company_id")
        except Exception:
            cid = None
    try:
        v = int(str(cid).strip())
        return v if v > 0 else None
    except Exception:
        return None


def resolve_company_plan(company_id: int) -> Optional[str]:
    """
    The company's active package: payroll_only | bookkeeping_only | combo,
    or None when the company has NO active package.

    Manual admin override wins; otherwise the live Stripe subscription's price.
    A Stripe/API error propagates (raises) so callers can fail open rather
    than treating an outage as "no subscription".
    """
    # 1. Manual override set by a platform admin.
    try:
        from models.company import Company

        company = db.session.get(Company, company_id)
        ov = (getattr(company, "plan_override", None) or "").strip().lower()
        if ov in CAPABILITY_PLANS_ALL:
            return ov
    except Exception:
        db.session.rollback()  # DB hiccup on override lookup -> ignore, try Stripe

    # 2. Live Stripe subscription -> price id -> package. Errors here propagate.
    from billing.checkout import _plan_key_for_price, _stripe_client
    from billing.customers import get_company_customer

    rec = get_company_customer(company_id)
    customer_id = (rec or {}).get("stripe_customer_id")
    if not customer_id:
        return None  # definitively no subscription

    stripe = _stripe_client()
    subs = stripe.Subscription.list(customer=customer_id, status="all", limit=10)
    items = subs.get("data") or []
    rank = {"active": 0, "trialing": 1, "past_due": 2, "unpaid": 3, "canceled": 4}
    items.sort(key=lambda s: rank.get(s.get("status"), 9))
    for sub in items:
        if sub.get("status") not in ("active", "trialing"):
            continue
        for li in (sub.get("items", {}).get("data") or []):
            pk = _plan_key_for_price((li.get("price") or {}).get("id") or "")
            if pk:
                return pk
    return None  # has a customer but no active package subscription


def company_has_capability(company_id: int, capability: str) -> bool:
    """
    True if the company's package includes the capability, False otherwise
    (including when it has no active subscription). Raises if the plan could
    not be resolved due to a Stripe/API error — callers fail open on that.
    """
    plan = resolve_company_plan(company_id)
    if plan is None:
        return False
    return plan in CAPABILITY_PLANS.get(capability, set())


def _needs_plan_response(capability: str, status: int = 402):
    plans = sorted(CAPABILITY_PLANS.get(capability, set()))
    labels = [PLAN_LABEL.get(p, p) for p in plans]
    return (
        jsonify(
            {
                "error": "plan_feature_unavailable",
                "capability": capability,
                "required_plans": plans,
                "message": f"Your plan does not include {capability}. "
                f"Subscribe to {' or '.join(labels)} to unlock it.",
                "checkout_hint": "/billing",
            }
        ),
        status,
    )


def require_plan(capability: str) -> Callable[[F], F]:
    """
    Gate a route on the real package capability. Allows when gating is off,
    and fails open on an unexpected resolution error so a Stripe outage never
    locks out a paying customer.
    """

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            if not _gating_enforced():
                return fn(*args, **kwargs)

            company_id = _extract_company_id()
            if company_id is None:
                return jsonify(
                    {
                        "error": "subscription_required",
                        "message": "Sign in with your company to access this feature.",
                    }
                ), 401

            try:
                has = company_has_capability(company_id, capability)
            except Exception:
                has = None  # resolution failure -> fail open

            if has is False:
                return _needs_plan_response(capability)
            # True or None (undeterminable) -> allow
            return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator

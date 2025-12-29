# File: billing/subscription_gate.py
# Timestamp: 2025-12-28 (CST)
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar, cast

from flask import jsonify, request

from billing.entitlement import ENTITLEMENTS_BYPASS, ENTITLEMENTS_ENABLED, PLAN_ENTITLEMENTS

F = TypeVar("F", bound=Callable[..., Any])


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _subscription_required_enabled() -> bool:
    # Master switch for subscription enforcement (independent of entitlements feature gating)
    return _truthy(os.getenv("SUBSCRIPTION_REQUIRED_ENABLED", "1"))


def _bypass_enabled() -> bool:
    # Subscription bypass (admin/emergency). Separate from ENTITLEMENTS_BYPASS.
    return _truthy(os.getenv("SUBSCRIPTION_BYPASS", "0"))


def _extract_customer_id() -> Optional[str]:
    cid = request.headers.get("X-Customer-Id")
    if cid and cid.strip():
        return cid.strip()

    cid = request.args.get("customer_id")
    if cid and cid.strip():
        return cid.strip()

    data = request.get_json(silent=True) or {}
    if isinstance(data, dict):
        cid2 = data.get("customer_id")
        if isinstance(cid2, str) and cid2.strip():
            return cid2.strip()

    return None


def _stripe_enabled() -> bool:
    return bool((os.getenv("STRIPE_SECRET_KEY") or "").strip())


def _stripe_import():
    import stripe  # type: ignore

    stripe.api_key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
    return stripe


def _cache_ttl_seconds() -> int:
    try:
        return max(5, int(os.getenv("SUBSCRIPTION_CACHE_TTL", "30")))
    except Exception:
        return 30


# In-memory cache (best-effort; safe for a single process)
# key: customer_id -> (expires_at, payload)
_SUB_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _normalize_feature_name(feature: str) -> str:
    f = feature.strip()
    if ":" in f:
        return f
    # allow caller to pass "payroll_run" and we normalize to "payroll:run"
    if "_" in f:
        parts = f.split("_", 1)
        if len(parts) == 2 and parts[0] and parts[1]:
            return f"{parts[0]}:{parts[1]}"
    return f


def _plan_from_price_id(price_id: Optional[str]) -> str:
    """
    Map Stripe price_id -> plan name using env vars.
    Set one or more of:
      STRIPE_PRICE_ID_STARTER
      STRIPE_PRICE_ID_PRO
      STRIPE_PRICE_ID_ENTERPRISE
    Default plan if unmatched:
      CUSTOMER_PLAN_DEFAULT (fallback "starter")
    """
    pid = (price_id or "").strip()
    if not pid:
        return (os.getenv("CUSTOMER_PLAN_DEFAULT") or "starter").strip() or "starter"

    if pid == (os.getenv("STRIPE_PRICE_ID_ENTERPRISE") or "").strip():
        return "enterprise"
    if pid == (os.getenv("STRIPE_PRICE_ID_PRO") or "").strip():
        return "pro"
    if pid == (os.getenv("STRIPE_PRICE_ID_STARTER") or "").strip():
        return "starter"

    return (os.getenv("CUSTOMER_PLAN_DEFAULT") or "starter").strip() or "starter"


def _feature_allowed(plan: str, feature: str) -> bool:
    f = _normalize_feature_name(feature)
    allowed = PLAN_ENTITLEMENTS.get(plan, set())
    if "*" in allowed:
        return True
    return f in allowed


@dataclass
class SubscriptionCheckResult:
    active: bool
    reason: str
    customer_id: str
    subscription_id: Optional[str] = None
    price_id: Optional[str] = None
    status: Optional[str] = None
    plan: Optional[str] = None


def _check_subscription_via_stripe(customer_id: str) -> SubscriptionCheckResult:
    if not _stripe_enabled():
        return SubscriptionCheckResult(
            active=False,
            reason="stripe_not_configured",
            customer_id=customer_id,
        )

    cached = _cache_get(customer_id)
    if cached:
        return SubscriptionCheckResult(
            active=bool(cached.get("active", False)),
            reason=str(cached.get("reason", "cached")),
            customer_id=customer_id,
            subscription_id=cached.get("subscription_id"),
            price_id=cached.get("price_id"),
            status=cached.get("status"),
            plan=cached.get("plan"),
        )

    try:
        stripe = _stripe_import()
        subs = stripe.Subscription.list(customer=customer_id, status="all", limit=10)
        data = subs.get("data") or []

        best = None
        for s in data:
            st = (s.get("status") or "").strip().lower()
            if st in {"active", "trialing"}:
                best = s
                break
        if best is None and data:
            best = data[0]

        if not best:
            payload = {
                "active": False,
                "reason": "no_subscription",
                "subscription_id": None,
                "price_id": None,
                "status": None,
                "plan": None,
            }
            _cache_set(customer_id, payload)
            return SubscriptionCheckResult(active=False, reason="no_subscription", customer_id=customer_id)

        status = (best.get("status") or "").strip().lower()
        price_id = _pick_primary_price_id(best)
        active = _is_subscription_active_status(status)
        plan = _plan_from_price_id(price_id) if active else None

        payload = {
            "active": active,
            "reason": "ok" if active else "inactive_subscription",
            "subscription_id": best.get("id"),
            "price_id": price_id,
            "status": status,
            "plan": plan,
        }
        _cache_set(customer_id, payload)

        return SubscriptionCheckResult(
            active=active,
            reason=payload["reason"],
            customer_id=customer_id,
            subscription_id=payload["subscription_id"],
            price_id=price_id,
            status=status,
            plan=plan,
        )

    except Exception:
        # Conservative failure: treat as not active when subscription is required
        return SubscriptionCheckResult(active=False, reason="stripe_error", customer_id=customer_id)


def require_active_subscription(_fn: Optional[F] = None, *, feature: Optional[str] = None) -> F:
    """
    Usage:
      @require_active_subscription
      @require_active_subscription()
      @require_active_subscription(feature="payroll:run")   (or "payroll_run")
    """

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Global off switch
            if not _subscription_required_enabled():
                return fn(*args, **kwargs)

            # Emergency bypass (service-level)
            if _bypass_enabled():
                return fn(*args, **kwargs)

            customer_id = _extract_customer_id()
            if not customer_id:
                return (
                    jsonify(
                        {
                            "error": "subscription_required",
                            "message": "Missing customer_id (X-Customer-Id header, query, or JSON).",
                        }
                    ),
                    401,
                )

            result = _check_subscription_via_stripe(customer_id)
            if not result.active:
                return (
                    jsonify(
                        {
                            "error": "subscription_inactive",
                            "message": "Active subscription required.",
                            "reason": result.reason,
                            "customer_id": customer_id,
                        }
                    ),
                    402,
                )

            # Feature gating (entitlements.py)
            if feature and ENTITLEMENTS_ENABLED and not ENTITLEMENTS_BYPASS:
                plan = (result.plan or "starter").strip() or "starter"
                if not _feature_allowed(plan, feature):
                    return (
                        jsonify(
                            {
                                "error": "feature_not_entitled",
                                "message": "Your plan does not include this feature.",
                                "feature": _normalize_feature_name(feature),
                                "plan": plan,
                            }
                        ),
                        403,
                    )

            return fn(*args, **kwargs)

        return cast(F, wrapper)

    if _fn is None:
        return cast(F, decorator)
    return decorator(_fn)


# Commit message:
# fix(subscription_gate): align imports with billing/entitlement.py and add robust plan+feature gating

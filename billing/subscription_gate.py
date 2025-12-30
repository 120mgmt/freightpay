# File: billing/subscription_gate.py
# Purpose: Production-ready subscription + entitlement gating
# Import target: from billing.subscription_gate import require_active_subscription

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar, cast

from flask import jsonify, request

from billing.entitlement import (
    Entitlements,
    entitlements_from_stripe_price_id,
    entitlements_to_dict,
    feature_enabled,
    subscription_required_enabled,
)

F = TypeVar("F", bound=Callable[..., Any])

# In-memory cache (best-effort; per-process). OK for single instance; safe fallback otherwise.
# customer_id -> (expires_at_epoch, payload_dict)
_SUB_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _truthy(v: Optional[str]) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _bypass_enabled() -> bool:
    # Emergency bypass. Keep OFF in production unless explicitly enabled.
    return _truthy(os.getenv("SUBSCRIPTION_BYPASS", "0"))


def _cache_ttl_seconds() -> int:
    try:
        # Default 30s; minimum 5s to avoid thrashing Stripe.
        return max(5, int((os.getenv("SUBSCRIPTION_CACHE_TTL", "30") or "30").strip()))
    except Exception:
        return 30


def _cache_get(customer_id: str) -> Optional[Dict[str, Any]]:
    now = time.time()
    item = _SUB_CACHE.get(customer_id)
    if not item:
        return None
    expires_at, payload = item
    if expires_at <= now:
        _SUB_CACHE.pop(customer_id, None)
        return None
    return payload


def _cache_set(customer_id: str, payload: Dict[str, Any]) -> None:
    _SUB_CACHE[customer_id] = (time.time() + _cache_ttl_seconds(), payload)


def _extract_customer_id() -> Optional[str]:
    # Priority: header -> query -> JSON body
    cid = request.headers.get("X-Customer-Id")
    if isinstance(cid, str) and cid.strip():
        return cid.strip()

    cid = request.args.get("customer_id")
    if isinstance(cid, str) and cid.strip():
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
    # Import Stripe only when needed to avoid crashing imports when gating is ON but Stripe isn't installed yet.

    import stripe  # type: ignore

    stripe.api_key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
    return stripe


def _pick_primary_price_id(subscription: Any) -> Optional[str]:
    """
    Stripe Subscription object -> first line item's Price ID (recurring plan).
    """
    try:
        items = subscription.get("items", {}).get("data", [])  # type: ignore[union-attr]
        if not items:
            return None
        price = items[0].get("price") or {}
        pid = price.get("id")
        if isinstance(pid, str) and pid.strip():
            return pid.strip()
        return None
    except Exception:
        return None


def _is_active_subscription_status(status: Optional[str]) -> bool:
    return (status or "").strip().lower() in {"active", "trialing"}


@dataclass
class SubscriptionCheckResult:
    active: bool
    reason: str
    customer_id: str
    entitlements: Optional[Entitlements] = None
    subscription_id: Optional[str] = None
    price_id: Optional[str] = None
    status: Optional[str] = None


def _rehydrate_entitlements(d: Any) -> Optional[Entitlements]:
    if not isinstance(d, dict):
        return None
    plan = d.get("plan")
    features = d.get("features")
    limits = d.get("limits")
    if not isinstance(plan, str):
        plan = "free"
    if not isinstance(features, dict):
        features = {}
    if not isinstance(limits, dict):
        limits = {}
    # Entitlements dataclass signature: (plan, features, limits)
    try:
        return Entitlements(plan=plan, features=dict(features), limits=dict(limits))
    except Exception:
        return None


def _check_subscription_via_stripe(customer_id: str) -> SubscriptionCheckResult:
    """
    Stripe-backed subscription status:
      - customer_id is expected to be a Stripe Customer ID (cus_...)
      - active = subscription status in {"active","trialing"}
      - entitlements derived from Stripe Price ID via entitlements_from_stripe_price_id
    """
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
            entitlements=_rehydrate_entitlements(cached.get("entitlements")),
            subscription_id=cached.get("subscription_id"),
            price_id=cached.get("price_id"),
            status=cached.get("status"),
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
                "entitlements": None,
            }
            _cache_set(customer_id, payload)
            return SubscriptionCheckResult(active=False, reason="no_subscription", customer_id=customer_id)

        status = (best.get("status") or "").strip().lower()
        price_id = _pick_primary_price_id(best)
        active = _is_active_subscription_status(status)

        ent = entitlements_from_stripe_price_id(price_id) if active else None

        payload = {
            "active": active,
            "reason": "ok" if active else "inactive_subscription",
            "subscription_id": best.get("id"),
            "price_id": price_id,
            "status": status,
            "entitlements": entitlements_to_dict(ent) if ent else None,
        }
        _cache_set(customer_id, payload)

        return SubscriptionCheckResult(
            active=active,
            reason=str(payload["reason"]),
            customer_id=customer_id,
            entitlements=ent,
            subscription_id=str(payload["subscription_id"]) if payload["subscription_id"] else None,
            price_id=price_id,
            status=status,
        )
    except Exception:
        # Conservative failure: if Stripe fails while gating is ON, deny.
        return SubscriptionCheckResult(active=False, reason="stripe_error", customer_id=customer_id)


def _allow_when_gating_off() -> bool:
    return not subscription_required_enabled()


def require_active_subscription(_fn: Optional[F] = None, *, feature: Optional[str] = None) -> F:
    """
    Works as:
      @require_active_subscription
      @require_active_subscription()
      @require_active_subscription(feature="payroll:run")
    """

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Gating OFF => allow
            if _allow_when_gating_off():
                return fn(*args, **kwargs)

            # Bypass ON => allow
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

            # Feature entitlement check (derived from price_id → plan)
            if feature:
                ent = result.entitlements
                if ent is None:
                    return (
                        jsonify(
                            {
                                "error": "entitlements_missing",
                                "message": "Entitlements could not be resolved for this subscription.",
                                "feature": feature,
                                "customer_id": customer_id,
                            }
                        ),
                        403,
                    )
                if not feature_enabled(ent, feature):
                    return (
                        jsonify(
                            {
                                "error": "feature_not_entitled",
                                "message": "Your plan does not include this feature.",
                                "feature": feature,
                                "plan": ent.plan,
                            }
                        ),
                        403,
                    )

            return fn(*args, **kwargs)

        return cast(F, wrapper)

    if _fn is None:
        return cast(F, decorator)  # used as @require_active_subscription(...)
    return decorator(_fn)  # used as @require_active_subscription


if __name__ == "__main__":
    # Minimal sanity (no Stripe calls). subscription_required_enabled() is controlled by billing/entitlement.py
    # Master switch is typically SUBSCRIPTION_REQUIRED (see billing/entitlement.py comments).
    os.environ["SUBSCRIPTION_REQUIRED"] = "0"
    assert subscription_required_enabled() is False

    os.environ["SUBSCRIPTION_REQUIRED"] = "1"
    assert subscription_required_enabled() is True

    os.environ["SUBSCRIPTION_BYPASS"] = "1"
    assert _bypass_enabled() is True

    os.environ["SUBSCRIPTION_BYPASS"] = "0"
    assert _bypass_enabled() is False


    print("billing/subscription_gate.py OK")

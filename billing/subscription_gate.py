# File: billing/subscription_gate.py
# Purpose: Enforce active Stripe subscription + plan entitlements with optional per-route feature gating.
# Required import usage:
#   from billing.subscription_gate import require_active_subscription

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


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _bypass_enabled() -> bool:
    # For internal testing only. Keep OFF in production.
    return _truthy(os.getenv("SUBSCRIPTION_BYPASS", "0"))


def _extract_customer_id() -> Optional[str]:
    # Priority: header -> query -> JSON
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


@dataclass
class SubscriptionCheckResult:
    active: bool
    reason: str
    customer_id: str
    entitlements: Optional[Entitlements] = None
    subscription_id: Optional[str] = None
    price_id: Optional[str] = None
    status: Optional[str] = None


# In-memory cache (best-effort; process-local)
# key: customer_id -> (expires_at_epoch, payload_dict)
_SUB_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _cache_ttl_seconds() -> int:
    try:
        return max(5, int(os.getenv("SUBSCRIPTION_CACHE_TTL", "30")))
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


def _pick_primary_price_id(subscription: Any) -> Optional[str]:
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


def _check_subscription_via_stripe(customer_id: str) -> SubscriptionCheckResult:
    # If Stripe isn't configured but gating is ON, we must block (production-safe).
    if not _stripe_enabled():
        return SubscriptionCheckResult(
            active=False,
            reason="stripe_not_configured",
            customer_id=customer_id,
        )

    cached = _cache_get(customer_id)
    if cached:
        ent = None
        ent_d = cached.get("entitlements")
        if isinstance(ent_d, dict):
            try:
                ent = Entitlements(
                    plan=str(ent_d.get("plan", "starter")),
                    features=dict(ent_d.get("features", {})),
                    limits=dict(ent_d.get("limits", {})),
                )
            except Exception:
                ent = None

        return SubscriptionCheckResult(
            active=bool(cached.get("active", False)),
            reason=str(cached.get("reason", "cached")),
            customer_id=customer_id,
            entitlements=ent,
            subscription_id=cached.get("subscription_id"),
            price_id=cached.get("price_id"),
            status=cached.get("status"),
        )

    try:
        stripe = _stripe_import()

        # Pull subscriptions by Stripe customer id
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
            subscription_id=payload.get("subscription_id"),
            price_id=price_id,
            status=status,
        )

    except Exception:
        # Conservative: if Stripe fails while gating is ON => block.
        return SubscriptionCheckResult(active=False, reason="stripe_error", customer_id=customer_id)


def _allow_when_gating_off() -> bool:
    return not subscription_required_enabled()


def require_active_subscription(_fn: Optional[F] = None, *, feature: Optional[str] = None) -> F:
    """
    Works as:
      @require_active_subscription
      @require_active_subscription()
      @require_active_subscription(feature="payroll_run")

    Behavior:
      - If SUBSCRIPTION_REQUIRED=0 => allow
      - If SUBSCRIPTION_BYPASS=1 => allow
      - Else:
          * require customer_id
          * require Stripe subscription active/trialing
          * if feature provided => require entitlement flag True
    """

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if _allow_when_gating_off():
                return fn(*args, **kwargs)

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

            if feature:
                ent = result.entitlements or entitlements_from_stripe_price_id(result.price_id)
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
    # Minimal sanity checks
    assert _truthy("1") is True
    assert _truthy("true") is True
    assert _truthy("YES") is True
    assert _truthy("0") is False
    assert _truthy("") is False
    assert _truthy(None) is False
    print("billing/subscription_gate.py OK")

                

    

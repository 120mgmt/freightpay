# billing/subscription_gate.py
from __future__ import annotations

import os
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

from flask import jsonify, request


def _truthy(v: Optional[str]) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _subscription_required_enabled() -> bool:
    # Default: OFF unless explicitly enabled
    return _truthy(os.getenv("SUBSCRIPTION_REQUIRED", "0"))


def _bypass_enabled() -> bool:
    # Default: ON in development, OFF otherwise (set explicitly if needed)
    env = (os.getenv("FLASK_ENV") or os.getenv("ENV") or "").lower()
    default = "1" if env in {"dev", "development", "local"} else "0"
    return _truthy(os.getenv("SUBSCRIPTION_BYPASS", default))


def _stripe_key() -> str:
    # Supports multiple common env names
    return (
        os.getenv("STRIPE_SECRET_KEY")
        or os.getenv("STRIPE_API_KEY")
        or os.getenv("STRIPE_SECRET")
        or ""
    )


def _extract_customer_id() -> str:
    # Accepts header, query, or json body
    return (
        request.headers.get("X-Stripe-Customer-Id", "")
        or request.args.get("customer_id", "")
        or (request.get_json(silent=True) or {}).get("customer_id", "")
        or ""
    ).strip()


def _extract_subscription_id() -> str:
    return (
        request.headers.get("X-Stripe-Subscription-Id", "")
        or request.args.get("subscription_id", "")
        or (request.get_json(silent=True) or {}).get("subscription_id", "")
        or ""
    ).strip()


def _check_stripe_active(customer_id: str, subscription_id: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Returns (is_active, meta)
    Active statuses: active, trialing
    """
    api_key = _stripe_key()
    if not api_key:
        return False, {"reason": "stripe_key_missing"}

    try:
        import stripe  # type: ignore
    except Exception:
        return False, {"reason": "stripe_library_missing"}

    stripe.api_key = api_key

    active_statuses = {"active", "trialing"}

    # Prefer subscription_id if provided
    if subscription_id:
        try:
            sub = stripe.Subscription.retrieve(subscription_id)
            status = (sub.get("status") or "").lower()
            return status in active_statuses, {
                "checked": "subscription_id",
                "status": status,
                "subscription_id": subscription_id,
            }
        except Exception as e:
            return False, {"checked": "subscription_id", "error": str(e)}

    # Otherwise check latest subscriptions for customer
    if customer_id:
        try:
            subs = stripe.Subscription.list(customer=customer_id, limit=10)
            data = subs.get("data", []) if isinstance(subs, dict) else getattr(subs, "data", [])
            for sub in data or []:
                status = (sub.get("status") or "").lower()
                if status in active_statuses:
                    return True, {
                        "checked": "customer_id",
                        "status": status,
                        "subscription_id": sub.get("id"),
                        "customer_id": customer_id,
                    }
            return False, {"checked": "customer_id", "reason": "no_active_subscription", "customer_id": customer_id}
        except Exception as e:
            return False, {"checked": "customer_id", "error": str(e)}

    return False, {"reason": "missing_customer_or_subscription_id"}


def require_active_subscription(fn: Callable[..., Any]) -> Callable[..., Any]:
    """
    Gate routes behind an active subscription when SUBSCRIPTION_REQUIRED=1.
    - Dev bypass: SUBSCRIPTION_BYPASS=1 (default in dev/local)
    - Provide either:
        - X-Stripe-Subscription-Id header, OR subscription_id param/json
        - X-Stripe-Customer-Id header, OR customer_id param/json
    """

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        if not _subscription_required_enabled():
            return fn(*args, **kwargs)

        if _bypass_enabled():
            return fn(*args, **kwargs)

        customer_id = _extract_customer_id()
        subscription_id = _extract_subscription_id()

        ok, meta = _check_stripe_active(customer_id=customer_id, subscription_id=subscription_id)
        if not ok:
            return (
                jsonify(
                    {
                        "error": "Subscription required",
                        "meta": meta,
                        "how_to_fix": "Provide active Stripe customer_id or subscription_id (headers or request body).",
                    }
                ),
                402,
            )

        return fn(*args, **kwargs)

    return wrapper

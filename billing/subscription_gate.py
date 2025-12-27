# Language: Python
# Problem: Provide a production-ready billing/subscription_gate.py that can be imported as:
#          from billing.subscription_gate import require_active_subscription
# Notes:
# - File MUST be named: billing/subscription_gate.py  (underscore, not a dot)
# - billing/ MUST contain __init__.py

from __future__ import annotations

import os
from functools import wraps
from typing import Any, Callable, TypeVar, cast

from flask import jsonify, request

F = TypeVar("F", bound=Callable[..., Any])


def _truthy(value: str | None) -> bool:
    """Parse common truthy strings safely."""
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _subscription_required_enabled() -> bool:
    """
    Master switch:
      SUBSCRIPTION_REQUIRED=1 => enforce gating
      SUBSCRIPTION_REQUIRED=0/empty => no gating
    """
    return _truthy(os.getenv("SUBSCRIPTION_REQUIRED", "0"))


def _bypass_enabled() -> bool:
    """
    Bypass switch (useful for internal testing):
      SUBSCRIPTION_BYPASS=1 => bypass gating
    Default: OFF in production; ON only if explicitly enabled.
    """
    return _truthy(os.getenv("SUBSCRIPTION_BYPASS", "0"))


def _extract_customer_id() -> str | None:
    """
    Extract a billing customer identifier from request.
    Priority:
      1) Header: X-Customer-Id
      2) Query:  customer_id
      3) JSON:   customer_id
    """
    cid = request.headers.get("X-Customer-Id")
    if cid:
        return cid.strip() or None

    cid = request.args.get("customer_id")
    if cid:
        return cid.strip() or None

    data = request.get_json(silent=True) or {}
    cid = data.get("customer_id")
    if isinstance(cid, str):
        return cid.strip() or None
    return None


def _is_active_subscription(customer_id: str) -> bool:
    """
    Production hook: replace this stub with a real Stripe lookup.
    For now, this is intentionally conservative:
      - If STRIPE is not configured, treat as NOT active when gating is enabled.
      - If you want to allow all until Stripe is wired, set SUBSCRIPTION_REQUIRED=0.
    """
    stripe_secret = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_secret:
        return False

    # TODO: Implement real Stripe subscription status check:
    # - Retrieve customer (or map customer_id to Stripe customer)
    # - Search active subscriptions
    # - Return True if status in {"active", "trialing"}
    #
    # Keeping stub behavior deterministic.
    return False


def require_active_subscription(fn: F) -> F:
    """
    Decorator to gate endpoints behind an active subscription.

    Behavior:
      - If SUBSCRIPTION_REQUIRED=0 => allow all requests (no gating)
      - If SUBSCRIPTION_REQUIRED=1 and SUBSCRIPTION_BYPASS=1 => allow all requests
      - If SUBSCRIPTION_REQUIRED=1 => require customer_id + active subscription
    """
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not _subscription_required_enabled():
            return fn(*args, **kwargs)

        if _bypass_enabled():
            return fn(*args, **kwargs)

        customer_id = _extract_customer_id()
        if not customer_id:
            return jsonify(
                {
                    "error": "subscription_required",
                    "message": "Missing customer_id (X-Customer-Id header, query, or JSON).",
                }
            ), 401

        if not _is_active_subscription(customer_id):
            return jsonify(
                {
                    "error": "subscription_inactive",
                    "message": "Active subscription required.",
                    "customer_id": customer_id,
                }
            ), 402

        return fn(*args, **kwargs)

    return cast(F, wrapper)


# Simple self-check (runs only if executed directly, not on import)
if __name__ == "__main__":
    # Minimal sanity checks for parsing logic
    assert _truthy("1") is True
    assert _truthy("true") is True
    assert _truthy("YES") is True
    assert _truthy("0") is False
    assert _truthy("") is False
    assert _truthy(None) is False

    os.environ["SUBSCRIPTION_REQUIRED"] = "0"
    assert _subscription_required_enabled() is False

    os.environ["SUBSCRIPTION_REQUIRED"] = "1"
    assert _subscription_required_enabled() is True

    os.environ["SUBSCRIPTION_BYPASS"] = "0"
    assert _bypass_enabled() is False

    os.environ["SUBSCRIPTION_BYPASS"] = "1"
    assert _bypass_enabled() is True

    print("subscription_gate.py self-checks: OK")

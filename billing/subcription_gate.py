# billing/subscription_gate.py
from __future__ import annotations

import os
from functools import wraps
from typing import Any, Callable

from flask import jsonify, request


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _subscription_required_enabled() -> bool:
    # Default OFF unless explicitly enabled
    return _truthy(os.getenv("SUBSCRIPTION_REQUIRED", "0"))


def _bypass_enabled() -> bool:
    # Default ON for dev/local, OFF otherwise
    env = (os.getenv("FLASK_ENV") or os.getenv("ENV") or "").lower()
    default = "1" if env in {"dev", "development", "local"} else "0"
    return _truthy(os.getenv("SUBSCRIPTION_BYPASS", default))


def require_active_subscription(fn: Callable[..., Any]):
    """
    Decorator to gate routes behind an active subscription.
    SAFE DEFAULTS:
      - Disabled unless SUBSCRIPTION_REQUIRED=1
      - Bypassed in dev/local unless explicitly disabled
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not _subscription_required_enabled():
            return fn(*args, **kwargs)

        if _bypass_enabled():
            return fn(*args, **kwargs)

        # Placeholder enforcement logic (Stripe / billing provider later)
        # Expect header or context indicating active subscription
        is_active = request.headers.get("X-Subscription-Active")

        if not _truthy(is_active):
            return (
                jsonify(
                    {
                        "error": "subscription_required",
                        "message": "Active subscription required to access this resource.",
                    }
                ),
                402,
            )

        return fn(*args, **kwargs)

    return wrapper

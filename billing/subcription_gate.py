# billing/subscription_gate.py
from __future__ import annotations

import os
from functools import wraps
from typing import Any, Callable

from flask import jsonify, request


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _subscription_required_enabled() -> bool:
    # OFF by default unless explicitly enabled
    return _truthy(os.getenv("SUBSCRIPTION_REQUIRED", "0"))


def _bypass_enabled() -> bool:
    # ON in dev/local, OFF otherwise unless explicitly set
    env = (os.getenv("FLASK_ENV") or os.getenv("ENV") or "").lower()
    default = "1" if env in {"dev", "development", "local"} else "0"
    return _truthy(os.getenv("SUBSCRIPTION_BYPASS", default))


def require_active_subscription(fn: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to gate endpoints behind an active subscription.

    Behavior:
    - If SUBSCRIPTION_REQUIRED=0 -> allow (no gating)
    - If SUBSCRIPTION_REQUIRED=1 and SUBSCRIPTION_BYPASS=1 -> allow
    - If SUBSCRIPTION_REQUIRED=1 and BYPASS is off -> require a simple signal:
        Header:  X-Subscription-Active: 1   (or true/yes/on)
        OR query param: subscription_active=1
    """
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        if not _subscription_required_enabled():
            return fn(*args, **kwargs)

        if _bypass_enabled():
            return fn(*args, **kwargs)

        active_header = request.headers.get("X-Subscription-Active")
        active_query = request.args.get("subscription_active")
        if _truthy(active_header) or _truthy(active_query):
            return fn(*args, **kwargs)

        return (
            jsonify(
                {
                    "error": "subscription_required",
                    "message": "Active subscription required to access this endpoint.",

                }
            ),
            402,
        )

    return wrapper

# billing/subscription_gate.py
from __future__ import annotations

import os
from functools import wraps
from typing import Callable, Any

from flask import jsonify, request


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _subscription_required_enabled() -> bool:
    # OFF by default unless explicitly enabled
    return _truthy(os.getenv("SUBSCRIPTION_REQUIRED", "0"))


def _bypass_enabled() -> bool:
    # ON in dev/local, OFF in prod unless explicitly overridden
    env = (os.getenv("FLASK_ENV") or os.getenv("ENV") or "").lower()
    default = "1" if env in {"dev", "development", "local"} else "0"
    return _truthy(os.getenv("SUBSCRIPTION_BYPASS", default))


def require_active_subscription(fn: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to gate endpoints behind an active subscription.

    Behavior:
    - If SUBSCRIPTION_REQUIRED=0 → always allow
    - If SUBSCRIPTION_REQUIRED=1:
        - Allow if SUBSCRIPTION_BYPASS=1 (dev/local)
        - Otherwise require a valid subscription (stubbed for now)
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not _subscription_required_enabled():
            return fn(*args, **kwargs)

        if _bypass_enabled():
            return fn(*args, **kwargs)

        # 🔒 Production subscription enforcement placeholder
        # Replace with Stripe / billing lookup when ready
        # For now, block access
        return (
            jsonify(
                {
                    "error": "Active subscription required",
                    "code": "SUBSCRIPTION_REQUIRED",
                }
            ),
            402,
        )

    return wrapper

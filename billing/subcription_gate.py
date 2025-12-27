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
    # ON in dev/local, OFF otherwise unless explicitly set
    env = (os.getenv("FLASK_ENV") or os.getenv("ENV") or "").lower()
    default = "1" if env in {"dev", "development", "local"} else "0"
    return _truthy(os.getenv("SUBSCRIPTION_BYPASS", default))


def require_active_subscription(fn: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to gate endpoints behind an active subscription.

    Behavior:
    - If SUBSCRIPTION_REQUIRED=0 → allow
    - If SUBSCRIPTION_BYPASS=1 → allow
    - Otherwise → require header X-Subscription-Active=true
      (placeholder until Stripe webhooks / customer lookup is wired)
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not _subscription_required_enabled():
            return fn(*args, **kwargs)

        if _bypass_enabled():
            return fn(*args, **kwargs)

        # Placeholder enforcement until Stripe customer lookup is wired
        header_val = request.headers.get("X-Subscription-Active")
        if _truthy(header_val):
            return fn(*args, **kwargs)

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


__all__ = ["require_active_subscription"]

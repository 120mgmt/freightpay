# billing/subscription_gate.py
from __future__ import annotations

import hmac
import os
from functools import wraps
from typing import Any, Callable, Optional, Tuple

from flask import jsonify, request

# ============================================================
# Subscription Gate (Production-Ready)
# - Default: OFF unless explicitly enabled
# - Supports safe bypass for dev/local only
# - Supports HMAC API key auth for internal/service-to-service use
# - Supports simple "active subscription" flag via env (until Stripe Connect is wired)
# ============================================================

# Env flags
# Turn gating ON in production by setting:
#   SUBSCRIPTION_REQUIRED=1
# Optional:
#   SUBSCRIPTION_BYPASS=0/1 (dev-only override)
#   FLASK_ENV / ENV used to detect dev/local
#
# API key support (recommended for internal calls):
#   SUBSCRIPTION_API_KEY=<long random secret>
# Header options (first match wins):
#   Authorization: Bearer <key>
#   X-API-Key: <key>
#
# Temporary hard gate (until Stripe subscription verification is implemented):
#   SUBSCRIPTION_FORCE_ACTIVE=1  -> treat all requests as active (useful during rollout)
#   SUBSCRIPTION_FORCE_ACTIVE=0  -> normal behavior


def _truthy(v: Optional[str]) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_name() -> str:
    return (os.getenv("FLASK_ENV") or os.getenv("ENV") or "").strip().lower()


def _subscription_required_enabled() -> bool:
    # OFF by default unless explicitly enabled
    return _truthy(os.getenv("SUBSCRIPTION_REQUIRED", "0"))


def _bypass_enabled() -> bool:
    # ON in dev/local only; OFF otherwise unless explicitly set
    env = _env_name()
    default = "1" if env in {"dev", "development", "local"} else "0"
    return _truthy(os.getenv("SUBSCRIPTION_BYPASS", default))


def _get_presented_api_key() -> Optional[str]:
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        key = auth.split(" ", 1)[1].strip()
        return key or None

    key = (request.headers.get("X-API-Key") or "").strip()
    return key or None


def _api_key_valid(presented: Optional[str]) -> bool:
    configured = (os.getenv("SUBSCRIPTION_API_KEY") or "").strip()
    if not configured:
        return False
    if not presented:
        return False
    # constant-time compare
    return hmac.compare_digest(presented, configured)


def _force_active() -> bool:
    return _truthy(os.getenv("SUBSCRIPTION_FORCE_ACTIVE", "0"))


def _request_has_active_subscription() -> Tuple[bool, str]:
    """
    Production contract:
      - If SUBSCRIPTION_FORCE_ACTIVE=1 -> allow (rollout mode)
      - Else if valid API key -> allow
      - Else require a client-provided subscription flag (until Stripe is wired):
          X-Subscription-Active: 1/true/yes/on
    """
    if _force_active():
        return True, "force_active"

    presented = _get_presented_api_key()
    if _api_key_valid(presented):
        return True, "api_key"

    header_flag = request.headers.get("X-Subscription-Active")
    if _truthy(header_flag):
        return True, "header_active"

    return False, "inactive_or_missing"


def require_active_subscription() -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to gate endpoints behind an active subscription.

    Behavior:
      - If SUBSCRIPTION_REQUIRED=0 -> allow (no gating)
      - If SUBSCRIPTION_BYPASS=1 AND env is dev/local -> allow (developer bypass)
      - Else enforce active subscription checks.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            if not _subscription_required_enabled():
                return fn(*args, **kwargs)

            env = _env_name()
            if _bypass_enabled() and env in {"dev", "development", "local"}:
                return fn(*args, **kwargs)

            ok, reason = _request_has_active_subscription()
            if not ok:
                return (
                    jsonify(
                        {
                            "error": "Active subscription required",
                            "code": "subscription_required",
                            "reason": reason,
                        }
                    ),
                    402,
                )

            return fn(*args, **kwargs)

        return wrapper

    return decorator

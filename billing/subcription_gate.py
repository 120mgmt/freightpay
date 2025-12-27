from __future__ import annotations

import os
from functools import wraps
from typing import Any, Callable, Tuple

from flask import jsonify, request

from billing.store import init_billing_db, is_subscription_active

# Initialize tables at import time (safe on Render; idempotent)
init_billing_db()

SUBSCRIPTION_REQUIRED = (os.getenv("SUBSCRIPTION_REQUIRED", "1") or "1").strip().lower() in {"1", "true", "yes", "on"}
ADMIN_BYPASS_TOKEN = (os.getenv("ADMIN_BYPASS_TOKEN", "") or "").strip()


def _company_id() -> str:
    return (request.headers.get("X-Company-Id") or os.getenv("DEFAULT_COMPANY_ID", "default")).strip()


def _admin_bypass_ok() -> bool:
    if not ADMIN_BYPASS_TOKEN:
        return False
    return (request.headers.get("X-Admin-Token") or "").strip() == ADMIN_BYPASS_TOKEN


def require_active_subscription(fn: Callable[..., Any]) -> Callable[..., Tuple[Any, int]]:
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        if not SUBSCRIPTION_REQUIRED:
            return fn(*args, **kwargs)

        if _admin_bypass_ok():
            return fn(*args, **kwargs)

        ok, reason = is_subscription_active(_company_id())
        if not ok:
            return jsonify({"error": {"code": "subscription_required", "reason": reason}}), 402

        return fn(*args, **kwargs)

    return wrapper

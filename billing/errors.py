# File: billing/errors.py
# Purpose: Standard billing error responses (stable codes, safe messages, production)
# Status: FULL PRODUCTION – hardened, deterministic, no secret leakage
# Date: 2026-01-26

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from flask import Response, jsonify


@dataclass(frozen=True)
class BillingError:
    code: str
    http_status: int
    message: str


# Canonical error catalog (stable API contract)
ERR = {
    "bad_request": BillingError("bad_request", 400, "Bad request."),
    "unauthorized": BillingError("unauthorized", 401, "Authentication required."),
    "forbidden": BillingError("forbidden", 403, "Forbidden."),
    "not_found": BillingError("not_found", 404, "Not found."),
    "conflict": BillingError("conflict", 409, "Conflict."),
    "rate_limited": BillingError("rate_limited", 429, "Too many requests."),
    "stripe_not_configured": BillingError("stripe_not_configured", 500, "Billing is not configured."),
    "stripe_signature_invalid": BillingError("stripe_signature_invalid", 400, "Invalid webhook signature."),
    "subscription_required": BillingError("subscription_required", 401, "Active subscription required."),
    "subscription_inactive": BillingError("subscription_inactive", 402, "Subscription inactive."),
    "feature_not_entitled": BillingError("feature_not_entitled", 403, "Feature not included in plan."),
    "server_error": BillingError("server_error", 500, "Server error."),
}


def _safe_detail(detail: Any) -> Optional[str]:
    """
    Keep this conservative. Never return secrets, keys, or raw exceptions to clients.
    """
    if detail is None:
        return None
    s = str(detail).strip()
    if not s:
        return None

    # Redact likely secrets (very conservative)
    lowered = s.lower()
    if "sk_live" in lowered or "sk_test" in lowered or "whsec_" in lowered or "api_key" in lowered:
        return None

    # Keep short
    return s[:300]


def error_response(
    code: str,
    *,
    message: Optional[str] = None,
    http_status: Optional[int] = None,
    detail: Any = None,
    **extra: Any,
) -> Tuple[Response, int]:
    """
    Returns (jsonify(payload), status_code)

    Payload schema:
      {
        "error": "<stable_code>",
        "message": "<safe_message>",
        "detail": "<optional_safe_detail>",
        ...extra
      }
    """
    be = ERR.get(code) or ERR["server_error"]

    payload: Dict[str, Any] = {
        "error": be.code,
        "message": (message or be.message),
    }

    d = _safe_detail(detail)
    if d:
        payload["detail"] = d

    if extra:
        payload.update(extra)

    status = int(http_status or be.http_status)
    return jsonify(payload), status


__all__ = ["error_response", "BillingError", "ERR"]

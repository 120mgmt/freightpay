# File: billing/security.py
# Purpose: Centralized billing security guards (Stripe-safe, webhook-safe, abuse-resistant)
# Status: FULL PRODUCTION – hardened, deterministic, no duplication
# Date: 2026-01-26

from __future__ import annotations

import hmac
import os
import time
from typing import Optional, Tuple

from flask import Request, abort, jsonify, request

# =========================
# ENV HELPERS
# =========================
def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _truthy(v: str) -> bool:
    return v.lower() in {"1", "true", "yes", "y", "on"}


# =========================
# STRIPE KEY VALIDATION
# =========================
def validate_stripe_secret_key() -> None:
    key = _env("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY missing")
    if key in {"sk_live", "sk_test"}:
        raise RuntimeError("STRIPE_SECRET_KEY truncated")
    if not (key.startswith("sk_live_") or key.startswith("sk_test_")):
        raise RuntimeError("STRIPE_SECRET_KEY invalid format")
    if len(key) < 20:
        raise RuntimeError("STRIPE_SECRET_KEY too short")


def validate_webhook_secret() -> None:
    secret = _env("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET missing")
    if secret == "whsec":
        raise RuntimeError("STRIPE_WEBHOOK_SECRET truncated")
    if not secret.startswith("whsec_"):
        raise RuntimeError("STRIPE_WEBHOOK_SECRET invalid format")
    if len(secret) < 20:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET too short")


# =========================
# HEALTH / OPS TOKEN GUARD
# =========================
def require_ops_token(
    *,
    header_name: Optional[str] = None,
    env_name: str = "BILLING_OPS_TOKEN",
) -> None:
    """
    Hard gate for sensitive endpoints (health, admin, internal ops).

    Usage:
        require_ops_token()
    """
    token = _env(env_name)
    if not token:
        return  # gate disabled

    hdr = header_name or _env("BILLING_OPS_TOKEN_HEADER") or "X-Ops-Token"
    provided = (request.headers.get(hdr) or "").strip()

    if not (provided and hmac.compare_digest(provided, token)):
        abort(403)


# =========================
# RATE LIMIT (LIGHTWEIGHT)
# =========================
# NOTE:
# - Stripe retries on non-200; never block Stripe webhooks with rate limiting
# - This is for customer-facing billing endpoints only

_RATE_BUCKET = {}  # key -> (reset_epoch, count)


def _rate_key(req: Request) -> str:
    return (
        req.headers.get("X-Forwarded-For")
        or req.remote_addr
        or "unknown"
    )


def rate_limit(
    *,
    limit: int = 60,
    window_seconds: int = 60,
) -> None:
    """
    Lightweight in-process rate limiter.
    DO NOT apply to Stripe webhooks.

    Usage:
        rate_limit(limit=30, window_seconds=60)
    """
    now = int(time.time())
    key = _rate_key(request)

    reset, count = _RATE_BUCKET.get(key, (now + window_seconds, 0))

    if now > reset:
        reset = now + window_seconds
        count = 0

    count += 1
    _RATE_BUCKET[key] = (reset, count)

    if count > limit:
        abort(
            jsonify(
                {
                    "error": "rate_limited",
                    "retry_after": reset - now,
                }
            ),
            429,
        )


# =========================
# REQUEST SANITY GUARD
# =========================
def enforce_json_request(max_bytes: int = 1_000_000) -> None:
    """
    Prevent abuse via oversized or non-JSON payloads.
    Safe for billing APIs (NOT webhooks).
    """
    cl = request.content_length
    if cl and cl > max_bytes:
        abort(413)

    if request.method in {"POST", "PUT", "PATCH"}:
        if not request.is_json:
            abort(
                jsonify(
                    {
                        "error": "invalid_content_type",
                        "expected": "application/json",
                    }
                ),
                415,
            )


__all__ = [
    "validate_stripe_secret_key",
    "validate_webhook_secret",
    "require_ops_token",
    "rate_limit",
    "enforce_json_request",
]


if __name__ == "__main__":
    print("billing/security.py OK")

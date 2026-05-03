# File: billing/stripe_client.py
# Purpose: Centralized Stripe config + env accessors (used across billing modules)
# Date: 2026-01-16
# Status: Production-hardened (strict key validation, safe env accessors)

from __future__ import annotations

import os
from typing import Optional

import stripe


def _get_env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def _require(name: str) -> str:
    v = _get_env(name)
    if not v:
        raise RuntimeError(f"Missing {name}")
    return v


def _validate_secret_key(key: str) -> None:
    # Prevent the exact failure you hit: "Invalid API Key provided: sk_live"
    if key in {"sk_live", "sk_test"}:
        raise RuntimeError("Invalid STRIPE_SECRET_KEY (truncated)")
    if not (key.startswith("sk_live_") or key.startswith("sk_test_")):
        raise RuntimeError("Invalid STRIPE_SECRET_KEY format (must start with sk_live_ or sk_test_)")
    if len(key) < 20:
        raise RuntimeError("Invalid STRIPE_SECRET_KEY (too short)")


def _validate_publishable_key(pk: str) -> None:
    if pk in {"pk_live", "pk_test"}:
        raise RuntimeError("Invalid STRIPE_PUBLISHABLE_KEY (truncated)")
    if not (pk.startswith("pk_live_") or pk.startswith("pk_test_")):
        raise RuntimeError("Invalid STRIPE_PUBLISHABLE_KEY format (must start with pk_live_ or pk_test_)")
    if len(pk) < 20:
        raise RuntimeError("Invalid STRIPE_PUBLISHABLE_KEY (too short)")


def _validate_webhook_secret(secret: str) -> None:
    # Stripe webhook signing secrets typically start with whsec_
    if secret in {"whsec"}:
        raise RuntimeError("Invalid STRIPE_WEBHOOK_SECRET (truncated)")
    if not secret.startswith("whsec_"):
        raise RuntimeError("Invalid STRIPE_WEBHOOK_SECRET format (must start with whsec_)")
    if len(secret) < 20:
        raise RuntimeError("Invalid STRIPE_WEBHOOK_SECRET (too short)")


def init_stripe() -> None:
    key = _require("STRIPE_SECRET_KEY")
    _validate_secret_key(key)
    stripe.api_key = key


def get_webhook_secret() -> str:
    secret = _require("STRIPE_WEBHOOK_SECRET")
    _validate_webhook_secret(secret)
    return secret


def get_publishable_key() -> str:
    pk = _require("STRIPE_PUBLISHABLE_KEY")
    _validate_publishable_key(pk)
    return pk


def get_default_currency() -> str:
    cur = (_get_env("STRIPE_CURRENCY", "usd") or "usd").strip().lower()
    return cur if cur else "usd"


def optional(v: Optional[str]) -> str:
    return (v or "").strip()


__all__ = [
    "init_stripe",
    "get_webhook_secret",
    "get_publishable_key",
    "get_default_currency",
    "optional",
]

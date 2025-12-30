# File: billing/stripe_client.py
# Purpose: Centralized Stripe config + env accessors (used across billing modules)

from __future__ import annotations

import os
from typing import Optional

import stripe


def _get_env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def init_stripe() -> None:
    key = _get_env("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("Missing STRIPE_SECRET_KEY")
    stripe.api_key = key


def get_webhook_secret() -> str:
    secret = _get_env("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise RuntimeError("Missing STRIPE_WEBHOOK_SECRET")
    return secret


def get_publishable_key() -> str:
    pk = _get_env("STRIPE_PUBLISHABLE_KEY")
    if not pk:
        raise RuntimeError("Missing STRIPE_PUBLISHABLE_KEY")
    return pk


def get_default_currency() -> str:
    return (_get_env("STRIPE_CURRENCY", "usd") or "usd").lower()


def optional(v: Optional[str]) -> str:
    return (v or "").strip()


__all__ = [
    "init_stripe",
    "get_webhook_secret",
    "get_publishable_key",
    "get_default_currency",
    "optional",
]

from __future__ import annotations

import os
from typing import Optional

import stripe


def init_stripe() -> None:
    key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing STRIPE_SECRET_KEY")
    stripe.api_key = key


def get_webhook_secret() -> str:
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise RuntimeError("Missing STRIPE_WEBHOOK_SECRET")
    return secret


def get_publishable_key() -> str:
    pk = os.getenv("STRIPE_PUBLISHABLE_KEY", "").strip()
    if not pk:
        raise RuntimeError("Missing STRIPE_PUBLISHABLE_KEY")
    return pk


def get_default_currency() -> str:
    return (os.getenv("STRIPE_CURRENCY", "usd") or "usd").strip().lower()


def optional(v: Optional[str]) -> str:
    return (v or "").strip()
    return val

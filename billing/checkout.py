# File: billing/checkout.py
# Purpose: Stripe Checkout entrypoints (creates Checkout Sessions for subscriptions)
# Imports: app.py expects: from billing.checkout import billing_bp

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

billing_bp = Blueprint("billing", __name__, url_prefix="/billing")


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name, default)
    if val is None:
        return None
    val = val.strip()
    return val if val else None


def _json_error(message: str, status: int = 400, **extra: Any):
    payload: Dict[str, Any] = {"error": message}
    payload.update(extra)
    return jsonify(payload), status


def _stripe_client():
    """
    Lazy import so the module can be imported even if Stripe isn't installed yet
    (but it should be installed via requirements.txt in production).
    """
    try:
        import stripe  # type: ignore
    except Exception as e:
        raise RuntimeError(f"Stripe library not available: {e}") from e

    secret = _get_env("STRIPE_SECRET_KEY")
    if not secret:
        raise RuntimeError("Missing STRIPE_SECRET_KEY env var")
    stripe.api_key = secret
    return stripe


def _base_url() -> str:
    # Prefer explicit env base URL; fallback to request host.
    explicit = _get_env("APP_BASE_URL")
    if explicit:
        return explicit.rstrip("/")
    return request.host_url.rstrip("/")


@billing_bp.get("/health")
def billing_health():
    return jsonify({"status": "ok"}), 200


@billing_bp.post("/checkout/session")
def create_checkout_session():
    """
    Creates a Stripe Checkout Session for a recurring subscription.

    Required env:
      - STRIPE_SECRET_KEY
      - STRIPE_PRICE_ID  (recurring price)
    Optional env:
      - APP_BASE_URL (e.g. https://freightpay.onrender.com)
      - STRIPE_SUCCESS_URL (defaults to {APP_BASE_URL}/dashboard?checkout=success)
      - STRIPE_CANCEL_URL  (defaults to {APP_BASE_URL}/billing?checkout=cancel)
      - STRIPE_CHECKOUT_ALLOW_PROMO_CODES (1/true/yes to enable)
      - STRIPE_DEFAULT_CURRENCY (default 'usd')
    """
    price_id = _get_env("STRIPE_PRICE_ID")
    if not price_id:
        return _json_error("Missing STRIPE_PRICE_ID env var", 500)

    # Caller can send email / customer_id; we can attach to Stripe customer later.
    data = request.get_json(silent=True) or {}
    customer_email = (data.get("email") or request.args.get("email") or "").strip() or None

    # URLs
    base = _base_url()
    success_url = _get_env("STRIPE_SUCCESS_URL", f"{base}/dashboard?checkout=success")
    cancel_url = _get_env("STRIPE_CANCEL_URL", f"{base}/billing?checkout=cancel")

    allow_promo = (_get_env("STRIPE_CHECKOUT_ALLOW_PROMO_CODES", "0") or "").lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }

    try:
        stripe = _stripe_client()

        session_kwargs: Dict[str, Any] = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "allow_promotion_codes": allow_promo,
        }

        if customer_email:
            session_kwargs["customer_email"] = customer_email

        # Metadata passthrough (optional)
        metadata = data.get("metadata")
        if isinstance(metadata, dict):
            # Convert to str->str defensively (Stripe metadata requirement)
            session_kwargs["metadata"] = {str(k): str(v) for k, v in metadata.items()}

        session = stripe.checkout.Session.create(**session_kwargs)

        return jsonify(
            {
                "id": session.get("id"),
                "url": session.get("url"),
            }
        ), 200

    except Exception as e:
        return _json_error("Failed to create checkout session", 500, detail=str(e))


@billing_bp.post("/checkout/session/one-time")
def create_one_time_checkout_session():
    """
    Optional: one-time payment checkout.
    Required env:
      - STRIPE_SECRET_KEY
      - STRIPE_ONE_TIME_PRICE_ID
    """
    price_id = _get_env("STRIPE_ONE_TIME_PRICE_ID")
    if not price_id:
        return _json_error("Missing STRIPE_ONE_TIME_PRICE_ID env var", 500)

    data = request.get_json(silent=True) or {}
    customer_email = (data.get("email") or request.args.get("email") or "").strip() or None

    base = _base_url()
    success_url = _get_env("STRIPE_SUCCESS_URL", f"{base}/dashboard?checkout=success")
    cancel_url = _get_env("STRIPE_CANCEL_URL", f"{base}/billing?checkout=cancel")

    try:
        stripe = _stripe_client()

        session_kwargs: Dict[str, Any] = {
            "mode": "payment",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
        }

        if customer_email:
            session_kwargs["customer_email"] = customer_email

        metadata = data.get("metadata")
        if isinstance(metadata, dict):
            session_kwargs["metadata"] = {str(k): str(v) for k, v in metadata.items()}

        session = stripe.checkout.Session.create(**session_kwargs)

        return jsonify({"id": session.get("id"), "url": session.get("url")}), 200

    except Exception as e:
        return _json_error("Failed to create one-time checkout session", 500, detail=str(e))


if __name__ == "__main__":
    # Minimal import-time sanity checks
    assert billing_bp.name == "billing"
    print("billing/checkout.py OK")


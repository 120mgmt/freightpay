# File: billing/checkout.py
# Purpose: Stripe Checkout entrypoints (creates Checkout Sessions for subscriptions)
# Import expectation (in app.py): from billing.checkout import billing_bp

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, jsonify, request

billing_bp = Blueprint("billing", __name__, url_prefix="/billing")


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name, default)
    if val is None:
        return None
    val = val.strip()
    return val if val else None


def _truthy(v: Optional[str]) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _json_error(message: str, status: int = 400, **extra: Any) -> Tuple[Any, int]:
    payload: Dict[str, Any] = {"error": message}
    payload.update(extra)
    return jsonify(payload), status


def _stripe_client():
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
    explicit = _get_env("APP_BASE_URL")
    if explicit:
        return explicit.rstrip("/")
    return request.host_url.rstrip("/")


def _extract_customer_id(data: Dict[str, Any]) -> Optional[str]:
    cid = request.headers.get("X-Customer-Id")
    if cid and cid.strip():
        return cid.strip()

    cid = data.get("customer_id")
    if isinstance(cid, str) and cid.strip():
        return cid.strip()

    cid = request.args.get("customer_id")
    if cid and cid.strip():
        return cid.strip()

    return None


@billing_bp.get("/health")
def billing_health():
    return jsonify({"status": "ok"}), 200


@billing_bp.post("/checkout/session")
def create_checkout_session():
    price_id = _get_env("STRIPE_PRICE_ID")
    if not price_id:
        return _json_error("Missing STRIPE_PRICE_ID env var", 500)

    data = request.get_json(silent=True)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return _json_error("Invalid JSON body. Send application/json.", 400)

    customer_email = (data.get("email") or request.args.get("email") or "")
    customer_email = customer_email.strip() or None

    customer_id = _extract_customer_id(data)

    base = _base_url()
    success_url = _get_env("STRIPE_SUCCESS_URL", f"{base}/dashboard?checkout=success")
    cancel_url = _get_env("STRIPE_CANCEL_URL", f"{base}/billing?checkout=cancel")

    allow_promo = _truthy(_get_env("STRIPE_CHECKOUT_ALLOW_PROMO_CODES", "0"))
    automatic_tax = _truthy(_get_env("STRIPE_CHECKOUT_AUTOMATIC_TAX", "0"))
    require_billing_address = _truthy(_get_env("STRIPE_REQUIRE_BILLING_ADDRESS", "0"))
    tax_id_collection = _truthy(_get_env("STRIPE_TAX_ID_COLLECTION", "0"))

    metadata_in = data.get("metadata")
    metadata: Optional[Dict[str, str]] = None
    if isinstance(metadata_in, dict):
        metadata = {str(k): str(v) for k, v in metadata_in.items()}

    cr_field = (_get_env("STRIPE_CLIENT_REFERENCE_ID_FIELD", "customer_id") or "customer_id").strip()
    client_reference_id = None
    if cr_field and isinstance(data.get(cr_field), (str, int)):
        client_reference_id = str(data.get(cr_field)).strip() or None
    if client_reference_id is None and customer_id:
        client_reference_id = customer_id

    try:
        stripe = _stripe_client()

        session_kwargs: Dict[str, Any] = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "allow_promotion_codes": allow_promo,
        }

        if customer_id:
            session_kwargs["customer"] = customer_id
        elif customer_email:
            session_kwargs["customer_email"] = customer_email

        if client_reference_id:
            session_kwargs["client_reference_id"] = client_reference_id

        if metadata:
            session_kwargs["metadata"] = metadata

        if automatic_tax:
            session_kwargs["automatic_tax"] = {"enabled": True}

        if require_billing_address:
            session_kwargs["billing_address_collection"] = "required"

        if tax_id_collection:
            session_kwargs["tax_id_collection"] = {"enabled": True}

        session = stripe.checkout.Session.create(**session_kwargs)
        return jsonify({"id": session.get("id"), "url": session.get("url")}), 200

    except Exception as e:
        return _json_error("Failed to create checkout session", 500, detail=str(e))


@billing_bp.post("/checkout/session/one-time")
def create_one_time_checkout_session():
    price_id = _get_env("STRIPE_ONE_TIME_PRICE_ID")
    if not price_id:
        return _json_error("Missing STRIPE_ONE_TIME_PRICE_ID env var", 500)

    data = request.get_json(silent=True)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return _json_error("Invalid JSON body. Send application/json.", 400)

    customer_email = (data.get("email") or request.args.get("email") or "")
    customer_email = customer_email.strip() or None

    customer_id = _extract_customer_id(data)

    base = _base_url()
    success_url = _get_env("STRIPE_SUCCESS_URL", f"{base}/dashboard?checkout=success")
    cancel_url = _get_env("STRIPE_CANCEL_URL", f"{base}/billing?checkout=cancel")

    automatic_tax = _truthy(_get_env("STRIPE_CHECKOUT_AUTOMATIC_TAX", "0"))
    require_billing_address = _truthy(_get_env("STRIPE_REQUIRE_BILLING_ADDRESS", "0"))
    tax_id_collection = _truthy(_get_env("STRIPE_TAX_ID_COLLECTION", "0"))

    metadata_in = data.get("metadata")
    metadata: Optional[Dict[str, str]] = None
    if isinstance(metadata_in, dict):
        metadata = {str(k): str(v) for k, v in metadata_in.items()}

    try:
        stripe = _stripe_client()

        session_kwargs: Dict[str, Any] = {
            "mode": "payment",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
        }

        if customer_id:
            session_kwargs["customer"] = customer_id
        elif customer_email:
            session_kwargs["customer_email"] = customer_email

        if metadata:
            session_kwargs["metadata"] = metadata

        if automatic_tax:
            session_kwargs["automatic_tax"] = {"enabled": True}

        if require_billing_address:
            session_kwargs["billing_address_collection"] = "required"

        if tax_id_collection:
            session_kwargs["tax_id_collection"] = {"enabled": True}

        session = stripe.checkout.Session.create(**session_kwargs)
        return jsonify({"id": session.get("id"), "url": session.get("url")}), 200

    except Exception as e:
        return _json_error("Failed to create one-time checkout session", 500, detail=str(e))


if __name__ == "__main__":
    assert billing_bp.name == "billing"
    print("billing/checkout.py OK")

# billing/customer_portal.py

from __future__ import annotations

import os
from typing import Any, Dict, Tuple

from flask import Blueprint, jsonify, request


portal_bp = Blueprint("portal", __name__, url_prefix="/billing/portal")


def _json_error(message: str, status: int = 400, **extra: Any) -> Tuple[Any, int]:
    payload: Dict[str, Any] = {"error": message}
    payload.update(extra)
    return jsonify(payload), status


def _stripe_client():
    try:
        import stripe  # type: ignore
    except Exception as e:
        raise RuntimeError(f"Stripe library not available: {e}") from e

    secret = os.getenv("STRIPE_SECRET_KEY")
    if not secret:
        raise RuntimeError("Missing STRIPE_SECRET_KEY env var")

    stripe.api_key = secret
    return stripe


@portal_bp.post("/session")
def create_customer_portal_session():
    """
    Creates a Stripe Customer Portal session so customers can:
    - Manage subscription
    - Update payment method
    - View invoices

    Required:
      - STRIPE_SECRET_KEY
      - customer_id (Stripe customer ID)

    Input:
      Header OR JSON:
        customer_id
    """

    data = request.get_json(silent=True) or {}

    customer_id = (
        request.headers.get("X-Customer-Id")
        or data.get("customer_id")
        or request.args.get("customer_id")
    )

    if not customer_id:
        return _json_error("Missing customer_id", 400)

    try:
        stripe = _stripe_client()

        return_url = os.getenv(
            "STRIPE_PORTAL_RETURN_URL",
            request.host_url.rstrip("/") + "/dashboard",
        )

        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )

        return jsonify({"url": session.get("url")}), 200

    except Exception as e:
        return _json_error("Failed to create portal session", 500, detail=str(e))


if __name__ == "__main__":
    assert portal_bp.name == "portal"
    print("billing/customer_portal.py OK")

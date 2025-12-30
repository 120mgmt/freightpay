# File: billing/store.py
# Purpose: Stripe Customer Portal + subscription status endpoints (production-ready)

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

store_bp = Blueprint("store", __name__, url_prefix="/store")


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name, default)
    if v is None:
        return None
    v = v.strip()
    return v if v else None

def get_customer(custtomer_id):
    import stripe
    return stripe.Customer.retrieve(customer_id)

def _stripe():
    try:
        import stripe  # type: ignore
    except Exception as e:
        raise RuntimeError(f"Stripe not installed: {e}") from e

    key = _env("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("Missing STRIPE_SECRET_KEY")
    stripe.api_key = key
    return stripe


def _base_url() -> str:
    explicit = _env("APP_BASE_URL")
    if explicit:
        return explicit.rstrip("/")
    return request.host_url.rstrip("/")


def _json_error(msg: str, status: int = 400, **extra: Any):
    payload: Dict[str, Any] = {"error": msg}
    payload.update(extra)
    return jsonify(payload), status


def _extract_customer_id() -> Optional[str]:
    cid = request.headers.get("X-Customer-Id")
    if cid and cid.strip():
        return cid.strip()

    cid = request.args.get("customer_id")
    if cid and cid.strip():
        return cid.strip()

    data = request.get_json(silent=True) or {}
    if isinstance(data, dict):
        cid2 = data.get("customer_id")
        if isinstance(cid2, str) and cid2.strip():
            return cid2.strip()
    return None


@store_bp.get("/health")
def store_health():
    return jsonify({"status": "ok"}), 200


@store_bp.post("/portal/session")
def create_customer_portal_session():
    """
    Creates a Stripe Customer Portal session.

    Required env:
      - STRIPE_SECRET_KEY

    Optional env:
      - APP_BASE_URL
      - STRIPE_PORTAL_RETURN_URL (defaults to {APP_BASE_URL}/dashboard)
    """
    customer_id = _extract_customer_id()
    if not customer_id:
        return _json_error(
            "Missing customer_id (X-Customer-Id header, query, or JSON).", 401
        )

    return_url = _env(
        "STRIPE_PORTAL_RETURN_URL", f"{_base_url()}/dashboard"
    )

    try:
        stripe = _stripe()
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return jsonify({"url": session.get("url")}), 200
    except Exception as e:
        return _json_error("Failed to create customer portal session", 500, detail=str(e))


@store_bp.get("/subscription/status")
def subscription_status():
    """
    Returns basic subscription status for a customer.

    Required env:
      - STRIPE_SECRET_KEY
    """
    customer_id = _extract_customer_id()
    if not customer_id:
        return _json_error(
            "Missing customer_id (X-Customer-Id header, query, or JSON).", 401
        )

    try:
        stripe = _stripe()
        subs = stripe.Subscription.list(customer=customer_id, status="all", limit=10)
        data = subs.get("data") or []

        active = False
        status = None
        price_id = None
        subscription_id = None

        for s in data:
            st = (s.get("status") or "").lower()
            if st in {"active", "trialing"}:
                active = True
                status = st
                subscription_id = s.get("id")
                items = s.get("items", {}).get("data", [])
                if items:
                    price = items[0].get("price") or {}
                    price_id = price.get("id")
                break

        return jsonify(
            {
                "customer_id": customer_id,
                "active": active,
                "status": status,
                "subscription_id": subscription_id,
                "price_id": price_id,
            }
        ), 200

    except Exception as e:
        return _json_error("Failed to fetch subscription status", 500, detail=str(e))


if __name__ == "__main__":
    assert store_bp.name == "store"
    print("billing/store.py OK")

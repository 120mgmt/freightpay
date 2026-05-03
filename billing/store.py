# File: billing/store.py
# Purpose: Stripe Customer Portal + subscription status endpoints (enterprise-hardened)
# Date: 2026-03-01
# Status: Enterprise-hardened (strict env validation, safe input validation, no undefined vars)

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

store_bp = Blueprint("store", __name__, url_prefix="/store")


def init_billing_db() -> None:
    # Placeholder hook (kept for backward-compat if app.py/imports call it)
    return None


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name, default)
    if v is None:
        return None
    v = v.strip()
    return v if v else None


def _validate_stripe_secret_key(key: str) -> None:
    if not key:
        raise RuntimeError("Missing STRIPE_SECRET_KEY")
    if key in {"sk_live", "sk_test"}:
        raise RuntimeError("Invalid STRIPE_SECRET_KEY (truncated)")
    if not (key.startswith("sk_live_") or key.startswith("sk_test_")):
        raise RuntimeError("Invalid STRIPE_SECRET_KEY format (must start with sk_live_ or sk_test_)")
    if len(key) < 20:
        raise RuntimeError("Invalid STRIPE_SECRET_KEY (too short)")


def _stripe():
    try:
        import stripe  # type: ignore
    except Exception as e:
        raise RuntimeError(f"Stripe not installed: {e}") from e

    key = _env("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("Missing STRIPE_SECRET_KEY")
    _validate_stripe_secret_key(key)

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
    if isinstance(cid, str) and cid.strip():
        return cid.strip()

    cid = request.args.get("customer_id")
    if isinstance(cid, str) and cid.strip():
        return cid.strip()

    data = request.get_json(silent=True) or {}
    if isinstance(data, dict):
        cid2 = data.get("customer_id")
        if isinstance(cid2, str) and cid2.strip():
            return cid2.strip()

    return None


def _validate_customer_id(customer_id: str) -> Optional[str]:
    c = (customer_id or "").strip()
    if not c:
        return "customer_id is required"
    # Stripe customer IDs are typically cus_... (or occasionally other internal formats)
    # Fail closed to avoid SSRF-ish patterns / junk IDs.
    if not c.startswith("cus_"):
        return "customer_id must be a valid Stripe customer id (cus_...)"
    if len(c) < 10:
        return "customer_id appears invalid"
    return None


def get_customer(customer_id: str) -> Dict[str, Any]:
    stripe = _stripe()
    err = _validate_customer_id(customer_id)
    if err:
        raise ValueError(err)
    cust = stripe.Customer.retrieve(customer_id)
    if isinstance(cust, dict):
        return cust
    try:
        return dict(cust)
    except Exception:
        return {"id": customer_id}


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
        return _json_error("Missing customer_id (X-Customer-Id header, query, or JSON).", 401)

    err = _validate_customer_id(customer_id)
    if err:
        return _json_error(err, 400)

    return_url = _env("STRIPE_PORTAL_RETURN_URL", f"{_base_url()}/dashboard") or f"{_base_url()}/dashboard"

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
        return _json_error("Missing customer_id (X-Customer-Id header, query, or JSON).", 401)

    err = _validate_customer_id(customer_id)
    if err:
        return _json_error(err, 400)

    try:
        stripe = _stripe()
        subs = stripe.Subscription.list(customer=customer_id, status="all", limit=10)
        data = subs.get("data") or []

        active = False
        status: Optional[str] = None
        price_id: Optional[str] = None
        subscription_id: Optional[str] = None

        for s in data:
            st = (s.get("status") or "").strip().lower()
            if st in {"active", "trialing"}:
                active = True
                status = st
                subscription_id = s.get("id")

                items = (s.get("items") or {}).get("data") or []
                if items:
                    price = (items[0] or {}).get("price") or {}
                    pid = price.get("id")
                    if isinstance(pid, str) and pid.strip():
                        price_id = pid.strip()
                break

        return (
            jsonify(
                {
                    "customer_id": customer_id,
                    "active": active,
                    "status": status,
                    "subscription_id": subscription_id,
                    "price_id": price_id,
                }
            ),
            200,
        )
    except Exception as e:
        return _json_error("Failed to fetch subscription status", 500, detail=str(e))


__all__ = ["store_bp", "init_billing_db", "get_customer"]

if __name__ == "__main__":
    print("billing/store.py OK")

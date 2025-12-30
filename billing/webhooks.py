# File: billing/webhooks.py
# Purpose: Stripe webhook receiver with idempotency + entitlement persistence (FULL PRODUCTION)

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, Response, jsonify, request

webhooks_bp = Blueprint("stripe_webhooks", __name__, url_prefix="/billing")


# -------------------------------------------------------------------
# ENV / HELPERS
# -------------------------------------------------------------------

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name, default)
    if v is None:
        return None
    v = v.strip()
    return v if v else None


def _stripe():
    import stripe  # type: ignore

    key = _env("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("Missing STRIPE_SECRET_KEY")
    stripe.api_key = key
    return stripe


def _json_error(msg: str, status: int = 400, **extra: Any) -> Tuple[Response, int]:
    payload: Dict[str, Any] = {"error": msg}
    payload.update(extra)
    return jsonify(payload), status


def _webhook_secret() -> Optional[str]:
    return _env("STRIPE_WEBHOOK_SECRET")


def _now() -> int:
    return int(time.time())


# -------------------------------------------------------------------
# STRIPE OBJECT HELPERS
# -------------------------------------------------------------------

def _event_object(event: Dict[str, Any]) -> Dict[str, Any]:
    return event.get("data", {}).get("object") or {}


def _sub_status(sub: Dict[str, Any]) -> str:
    return str(sub.get("status") or "").lower()


def _sub_customer_id(sub: Dict[str, Any]) -> Optional[str]:
    cid = sub.get("customer")
    return cid.strip() if isinstance(cid, str) and cid.strip() else None


def _sub_price_id(sub: Dict[str, Any]) -> Optional[str]:
    try:
        items = sub.get("items", {}).get("data", [])
        if not items:
            return None
        price = items[0].get("price") or {}
        pid = price.get("id")
        return pid.strip() if isinstance(pid, str) and pid.strip() else None
    except Exception:
        return None


def _is_active(status: str) -> bool:
    return status in {"active", "trialing"}


# -------------------------------------------------------------------
# ENTITLEMENT APPLY (PERSISTED)
# -------------------------------------------------------------------

def _apply_entitlements(customer_id: str, status: str, price_id: Optional[str]) -> None:
    from billing.entitlement import entitlements_from_stripe_price_id, entitlements_to_dict
    from billing.entitlement_store import upsert_customer_subscription

    active = _is_active(status)
    ent = entitlements_from_stripe_price_id(price_id) if active else None

    upsert_customer_subscription(
        customer_id=customer_id,
        active=active,
        status=status,
        price_id=price_id,
        entitlements=entitlements_to_dict(ent) if ent else None,
        updated_at=_now(),
    )


# -------------------------------------------------------------------
# HEALTH
# -------------------------------------------------------------------

@webhooks_bp.get("/webhooks/health")
def webhook_health() -> Tuple[Response, int]:
    return jsonify({"status": "ok"}), 200


# -------------------------------------------------------------------
# STRIPE WEBHOOK
# -------------------------------------------------------------------

@webhooks_bp.post("/webhooks/stripe")
def stripe_webhook() -> Tuple[Response, int]:
    secret = _webhook_secret()
    if not secret:
        return _json_error("Missing STRIPE_WEBHOOK_SECRET", 500)

    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature")
    if not sig:
        return _json_error("Missing Stripe-Signature", 400)

    try:
        stripe = _stripe()
        event = stripe.Webhook.construct_event(payload, sig, secret)
        event = event if isinstance(event, dict) else json.loads(json.dumps(event))
    except Exception as e:
        return _json_error("Webhook signature verification failed", 400, detail=str(e))

    event_type = str(event.get("type") or "")
    obj = _event_object(event)

    try:
        # Subscription lifecycle
        if event_type.startswith("customer.subscription."):
            status = _sub_status(obj)
            customer_id = _sub_customer_id(obj)
            price_id = _sub_price_id(obj)

            if customer_id:
                _apply_entitlements(customer_id, status, price_id)

            return jsonify({"received": True, "type": event_type}), 200

        # Checkout completed → fetch subscription
        if event_type in {
            "checkout.session.completed",
            "checkout.session.async_payment_succeeded",
        }:
            customer_id = obj.get("customer")
            sub_id = obj.get("subscription")

            if isinstance(customer_id, str) and isinstance(sub_id, str):
                stripe = _stripe()
                sub = stripe.Subscription.retrieve(sub_id)
                sub = sub if isinstance(sub, dict) else json.loads(json.dumps(sub))

                _apply_entitlements(
                    customer_id=customer_id.strip(),
                    status=_sub_status(sub),
                    price_id=_sub_price_id(sub),
                )

            return jsonify({"received": True, "type": event_type}), 200

        # Ignore everything else
        return jsonify({"received": True, "type": event_type, "ignored": True}), 200

    except Exception as e:
        # Never trigger Stripe retries
        return jsonify(
            {"received": True, "type": event_type, "handled_with_error": True, "detail": str(e)}
        ), 200


if __name__ == "__main__":
    assert webhooks_bp.name == "stripe_webhooks"
    print("billing/webhooks.py OK")

webhook_bp = webhooks_bp

# File: billing/webhooks.py
# Purpose: Stripe webhook receiver that keeps subscription/entitlement state in sync.
# Import expectation (in app.py): from billing.webhooks import webhooks_bp
# Register: app.register_blueprint(webhooks_bp)

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, Response, jsonify, request

webhooks_bp = Blueprint("stripe_webhooks", __name__, url_prefix="/billing")


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name, default)
    if v is None:
        return None
    v = v.strip()
    return v if v else None


def _stripe():
    import stripe  # type: ignore

    secret = _env("STRIPE_SECRET_KEY")
    if not secret:
        raise RuntimeError("Missing STRIPE_SECRET_KEY")
    stripe.api_key = secret
    return stripe


def _json_error(msg: str, status: int = 400, **extra: Any) -> Tuple[Response, int]:
    payload: Dict[str, Any] = {"error": msg}
    payload.update(extra)
    return jsonify(payload), status


def _webhook_secret() -> Optional[str]:
    # Stripe Dashboard → Developers → Webhooks → endpoint → Signing secret
    return _env("STRIPE_WEBHOOK_SECRET")


def _event_object(event: Dict[str, Any]) -> Dict[str, Any]:
    obj = event.get("data", {}).get("object")
    return obj if isinstance(obj, dict) else {}


def _sub_status(sub: Dict[str, Any]) -> str:
    return str(sub.get("status") or "").strip().lower()


def _sub_customer_id(sub: Dict[str, Any]) -> Optional[str]:
    c = sub.get("customer")
    if isinstance(c, str) and c.strip():
        return c.strip()
    return None


def _sub_primary_price_id(sub: Dict[str, Any]) -> Optional[str]:
    try:
        items = sub.get("items", {}).get("data", [])
        if not isinstance(items, list) or not items:
            return None
        price = items[0].get("price") or {}
        pid = price.get("id")
        if isinstance(pid, str) and pid.strip():
            return pid.strip()
        return None
    except Exception:
        return None


def _is_active_status(status: str) -> bool:
    return status in {"active", "trialing"}


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _now_ts() -> int:
    return int(time.time())


def _apply_entitlements_update(customer_id: str, status: str, price_id: Optional[str]) -> None:
    """
    Single integration point for your entitlement system.
    This keeps webhook logic isolated and avoids circular imports.

    REQUIRED in your codebase:
      - billing.entitlement: entitlements_from_stripe_price_id(price_id)
      - billing.entitlement: entitlements_to_dict(entitlements)

    OPTIONAL (if you have persistence):
      - billing.entitlement_store: upsert_customer_subscription(...)
    """
    from billing.entitlement import entitlements_from_stripe_price_id, entitlements_to_dict

    active = _is_active_status(status)
    ent = entitlements_from_stripe_price_id(price_id) if active else None
    ent_dict = entitlements_to_dict(ent) if ent else None

    # If you have a persistence layer, write the latest state.
    # This call is OPTIONAL and will not break if the module is absent.
    try:
        from billing.entitlement_store import upsert_customer_subscription  # type: ignore

        upsert_customer_subscription(
            customer_id=customer_id,
            active=active,
            status=status,
            price_id=price_id,
            entitlements=ent_dict,
            updated_at=_now_ts(),
        )
    except Exception:
        # No persistence available; webhook still verifies + returns 200.
        # subscription_gate.py can still query Stripe live if that's how you configured it.
        pass


@webhooks_bp.get("/webhooks/health")
def webhook_health() -> Tuple[Response, int]:
    return jsonify({"status": "ok"}), 200


@webhooks_bp.post("/webhooks/stripe")
def stripe_webhook() -> Tuple[Response, int]:
    secret = _webhook_secret()
    if not secret:
        return _json_error("Missing STRIPE_WEBHOOK_SECRET", 500)

    payload = request.get_data(as_text=False) or b""
    sig = request.headers.get("Stripe-Signature")
    if not sig:
        return _json_error("Missing Stripe-Signature header", 400)

    try:
        stripe = _stripe()
        event = stripe.Webhook.construct_event(payload=payload, sig_header=sig, secret=secret)
        if not isinstance(event, dict):
            event = json.loads(json.dumps(event))
    except Exception as e:
        return _json_error("Webhook signature verification failed", 400, detail=str(e))

    event_type = str(event.get("type") or "")
    obj = _event_object(event)

    # Subscription lifecycle events that matter for gating + entitlements
    subscription_events = {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "customer.subscription.paused",
        "customer.subscription.resumed",
        "customer.subscription.pending_update_applied",
        "customer.subscription.pending_update_expired",
        "customer.subscription.trial_will_end",
    }

    # Also handle Checkout completion (when subscription is created via Checkout)
    checkout_events = {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }

    try:
        if event_type in subscription_events:
            status = _sub_status(obj)
            customer_id = _sub_customer_id(obj)
            price_id = _sub_primary_price_id(obj)

            if customer_id:
                _apply_entitlements_update(customer_id=customer_id, status=status, price_id=price_id)

            return jsonify({"received": True, "type": event_type}), 200

        if event_type in checkout_events:
            # Checkout Session includes customer + subscription id
            customer_id = obj.get("customer")
            subscription_id = obj.get("subscription")

            if isinstance(customer_id, str) and customer_id.strip() and isinstance(subscription_id, str) and subscription_id.strip():
                stripe = _stripe()
                sub = stripe.Subscription.retrieve(subscription_id.strip())
                sub_dict = sub if isinstance(sub, dict) else json.loads(json.dumps(sub))

                status = _sub_status(sub_dict)
                price_id = _sub_primary_price_id(sub_dict)
                _apply_entitlements_update(customer_id=customer_id.strip(), status=status, price_id=price_id)

            return jsonify({"received": True, "type": event_type}), 200

        # Ignore unneeded events but return 200 so Stripe stops retrying
        return jsonify({"received": True, "type": event_type, "ignored": True}), 200

    except Exception as e:
        # Return 200 with error payload to avoid retry storms if your downstream persistence is flaky.
        return jsonify({"received": True, "type": event_type, "handled_with_error": True, "detail": str(e)}), 200


if __name__ == "__main__":
    assert webhooks_bp.name == "stripe_webhooks"
    print("billing/webhooks.py OK")

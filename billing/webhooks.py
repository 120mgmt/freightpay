from __future__ import annotations

from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

from billing.plans import load_plans
from billing.store import init_billing_db, upsert_subscription
from billing.stripe_client import get_webhook_secret, init_stripe
import stripe

webhook_bp = Blueprint("stripe_webhooks_v1", __name__, url_prefix="/stripe")

init_billing_db()
init_stripe()


def _plan_code_from_price(price_id: str) -> str:
    plans = load_plans()
    for code, plan in plans.items():
        if plan.price_id == price_id:
            return code
    return ""


def _extract_subscription_fields(sub: stripe.Subscription) -> Dict[str, Any]:
    price_id = ""
    try:
        if sub["items"]["data"]:
            price_id = sub["items"]["data"][0]["price"]["id"]
    except Exception:
        price_id = ""

    company_id = ""
    try:
        company_id = (sub.get("metadata") or {}).get("company_id", "") or ""
    except Exception:
        company_id = ""

    plan_code = (sub.get("metadata") or {}).get("plan_code", "") or _plan_code_from_price(price_id)

    current_period_end = None
    try:
        current_period_end = int(sub.get("current_period_end") or 0) or None
    except Exception:
        current_period_end = None

    cancel_at_period_end = bool(sub.get("cancel_at_period_end") or False)

    return {
        "company_id": company_id,
        "stripe_customer_id": sub.get("customer", "") or "",
        "stripe_subscription_id": sub.get("id", "") or "",
        "status": (sub.get("status", "") or "").lower(),
        "cancel_at_period_end": cancel_at_period_end,
        "current_period_end": current_period_end,
        "price_id": price_id,
        "plan_code": plan_code or "",
        "latest_invoice_id": sub.get("latest_invoice", "") or "",
    }


@webhook_bp.route("/webhook", methods=["POST"])
def stripe_webhook():
    secret = get_webhook_secret()
    payload = request.get_data(as_text=False)
    sig = request.headers.get("Stripe-Signature", "")

    try:
        event = stripe.Webhook.construct_event(payload=payload, sig_header=sig, secret=secret)
    except Exception as e:
        return jsonify({"error": f"webhook signature verification failed: {str(e)}"}), 400

    etype = event.get("type", "")
    data_obj: Optional[Dict[str, Any]] = None
    try:
        data_obj = event["data"]["object"]
    except Exception:
        data_obj = None

    # Handle subscription lifecycle events
    if etype in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    } and data_obj:
        sub = stripe.Subscription.retrieve(data_obj["id"])
        fields = _extract_subscription_fields(sub)

        if not fields["company_id"]:
            # If metadata missing, still record by customer id (company must be reconciled later)
            fields["company_id"] = (sub.get("metadata") or {}).get("company_id", "") or ""

        if not fields["company_id"]:
            # Hard fail safe: do not write orphan subscription
            return jsonify({"ignored": True, "reason": "missing_company_id_metadata"}), 200

        upsert_subscription(
            company_id=fields["company_id"],
            status=fields["status"],
            stripe_customer_id=fields["stripe_customer_id"],
            stripe_subscription_id=fields["stripe_subscription_id"],
            cancel_at_period_end=fields["cancel_at_period_end"],
            current_period_end=fields["current_period_end"],
            price_id=fields["price_id"],
            plan_code=fields["plan_code"],
            latest_invoice_id=fields["latest_invoice_id"],
            meta={"event": etype},
        )
        return jsonify({"ok": True}), 200

    # Payment failures -> mark as past_due if subscription exists
    if etype in {"invoice.payment_failed"} and data_obj:
        sub_id = data_obj.get("subscription") or ""
        if sub_id:
            sub = stripe.Subscription.retrieve(sub_id)
            fields = _extract_subscription_fields(sub)
            if fields["company_id"]:
                upsert_subscription(
                    company_id=fields["company_id"],
                    status=(fields["status"] or "past_due"),
                    stripe_customer_id=fields["stripe_customer_id"],
                    stripe_subscription_id=fields["stripe_subscription_id"],
                    cancel_at_period_end=fields["cancel_at_period_end"],
                    current_period_end=fields["current_period_end"],
                    price_id=fields["price_id"],
                    plan_code=fields["plan_code"],
                    latest_invoice_id=data_obj.get("id", "") or fields["latest_invoice_id"],
                    meta={"event": etype},
                )
        return jsonify({"ok": True}), 200

    # Checkout completion (customer + subscription are created)
    if etype == "checkout.session.completed" and data_obj:
        # Stripe will follow with subscription.created/updated; nothing required here.
        return jsonify({"ok": True}), 200

    return jsonify({"ok": True, "ignored": True, "type": etype}), 200

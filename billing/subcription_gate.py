# billing/subscription_gate.py

import os
import stripe
from functools import wraps
from flask import request, jsonify

# Stripe configuration
stripe.api_key = os.getenv("STRIPE_API_KEY")

PRICE_IDS = {
    "basic": os.getenv("STRIPE_PRICE_BASIC"),
    "pro": os.getenv("STRIPE_PRICE_PRO"),
    "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE"),
}


def _get_customer_id():
    # Priority: Header → JSON → Query param
    cid = request.headers.get("X-Stripe-Customer-Id")
    if cid:
        return cid

    payload = request.get_json(silent=True) or {}
    if isinstance(payload, dict) and payload.get("customer_id"):
        return payload["customer_id"]

    return request.args.get("customer_id")


def _has_active_subscription(customer_id: str) -> bool:
    if not customer_id or not stripe.api_key:
        return False

    subs = stripe.Subscription.list(
        customer=customer_id,
        status="active",
        expand=["data.items"],
        limit=10,
    )

    valid_prices = {pid for pid in PRICE_IDS.values() if pid}

    for sub in subs.data:
        for item in sub["items"]["data"]:
            if item["price"]["id"] in valid_prices:
                return True

    return False


def require_active_subscription():
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            customer_id = _get_customer_id()
            if not customer_id:
                return jsonify({"error": "Missing Stripe customer_id"}), 401

            if not _has_active_subscription(customer_id):
                return jsonify({"error": "Active subscription required"}), 402

            return fn(*args, **kwargs)
        return wrapper
    return decorator

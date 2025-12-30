# File: billing/customer_portal.py
# Purpose: Stripe Customer Portal access for existing subscribers
# Imported by app.py as: from billing.customer_portal import portal_bp

from __future__ import annotations

import os
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from billing.store import get_customer, init_billing_db
from billing.stripe_client import init_stripe

import stripe  # must be installed in production


portal_bp = Blueprint("billing_portal_v1", __name__, url_prefix="/billing")

# Ensure billing storage + Stripe are initialized once at import
init_billing_db()
init_stripe()


def _company_id() -> str:
    """
    Resolve company identifier.
    Priority:
      1. X-Company-Id header
      2. DEFAULT_COMPANY_ID env
    """
    return (
        request.headers.get("X-Company-Id")
        or os.getenv("DEFAULT_COMPANY_ID", "default")
    ).strip()


@portal_bp.post("/portal/session")
def create_portal_session():
    """
    POST /billing/portal/session

    Body:
      {
        "return_url": "https://app.example.com/dashboard"
      }

    Requires:
      - Existing Stripe customer mapped to company
      - STRIPE_SECRET_KEY env (handled in stripe_client)
    """
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    return_url = (data.get("return_url") or "").strip()

    if not return_url:
        return jsonify({"error": "return_url required"}), 400

    cust = get_customer(_company_id())
    if not cust:
        return jsonify({"error": "customer not found"}), 404

    try:
        session = stripe.billing_portal.Session.create(
            customer=cust["stripe_customer_id"],
            return_url=return_url,
        )
        return jsonify({"portal_url": session.url}), 200
    except Exception as e:
        return jsonify({"error": "failed to create portal session", "detail": str(e)}), 500

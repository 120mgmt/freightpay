# routes/bank_connections.py
# STRIPE FINANCIAL CONNECTIONS — ONBOARDING + CALLBACK (production-ready)

from __future__ import annotations

import os
from flask import Blueprint, request, jsonify
import stripe

# =========================
# Config
# =========================
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
BASE_URL = os.getenv("BASE_URL")  # e.g. https://api.ledgerhaul.com

if not STRIPE_SECRET_KEY:
    raise RuntimeError("Missing STRIPE_SECRET_KEY")

stripe.api_key = STRIPE_SECRET_KEY

bank_connections_bp = Blueprint("bank_connections", __name__, url_prefix="/bank")


# =========================
# Create Financial Connections Session
# =========================
@bank_connections_bp.route("/connect", methods=["POST"])
def create_bank_connection():
    """
    Starts Stripe Financial Connections flow.
    Client should redirect user to returned url.
    """

    data = request.json or {}
    company_id = data.get("company_id")

    if not company_id:
        return jsonify({"error": "company_id required"}), 400

    session = stripe.financial_connections.Session.create(
        account_holder={
            "type": "business",
        },
        permissions=["transactions", "balances", "ownership"],
        filters={
            "countries": ["US"],
        },
        return_url=f"{BASE_URL}/bank/return?company_id={company_id}",
    )

    return jsonify(
        {
            "session_id": session.id,
            "url": session.url,
        }
    )


# =========================
# Return Handler
# =========================
@bank_connections_bp.route("/return", methods=["GET"])
def bank_return():
    """
    Stripe redirects here after user completes bank linking.
    Client should call /bank/accounts to fetch linked accounts.
    """
    company_id = request.args.get("company_id")
    return jsonify(
        {
            "status": "connected",
            "company_id": company_id,
            "next": "Call /bank/accounts to list Financial Connections accounts",
        }
    )


# =========================
# List Linked Bank Accounts
# =========================
@bank_connections_bp.route("/accounts", methods=["GET"])
def list_bank_accounts():
    """
    Lists Financial Connections accounts linked to the platform.
    """
    accounts = stripe.financial_connections.Account.list(limit=100)

    return jsonify(
        {
            "accounts": [
                {
                    "id": a.id,
                    "institution_name": a.institution_name,
                    "last4": a.last4,
                    "status": a.status,
                }
                for a in accounts.data
            ]
        }
    )

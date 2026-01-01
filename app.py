# app.py
# FreightPay – Full Production Deployment v5
# Date: 2026-01-01
# Status: Production-ready

import os
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import stripe

# =========================
# App Initialization
# =========================
app = Flask(__name__)
CORS(app)

# =========================
# Environment Variables
# =========================
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
APP_ENV = os.getenv("APP_ENV", "production")
BASE_URL = os.getenv("BASE_URL", "https://freightpay.onrender.com")

if not STRIPE_SECRET_KEY or not STRIPE_WEBHOOK_SECRET:
    raise RuntimeError("Stripe environment variables are missing")

stripe.api_key = STRIPE_SECRET_KEY

# =========================
# PRICING – CORRECTED (FINAL)
# =========================
PRICING = {
    "combo": {
        "name": "Payroll + Bookkeeping",
        "base_price_cents": 9900,      # $99.00
        "per_employee_cents": 600,     # $6.00 per employee
        "currency": "usd"
    },
    "payroll_only": {
        "name": "Payroll Only",
        "base_price_cents": 4900,      # $49.00
        "per_employee_cents": 800,     # $8.00 per employee
        "currency": "usd"
    },
    "bookkeeping_only": {
        "name": "Bookkeeping Only",
        "base_price_cents": 6900,      # $69.00
        "per_employee_cents": 0,       # no per-employee charge
        "currency": "usd"
    }
}

# =========================
# Health Check
# =========================
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "env": APP_ENV,
        "timestamp": datetime.utcnow().isoformat()
    })

# =========================
# Stripe Checkout
# =========================
@app.route("/billing/checkout", methods=["POST"])
def create_checkout():
    data = request.json or {}
    plan_key = data.get("plan")
    employees = int(data.get("employees", 0))

    if plan_key not in PRICING:
        return jsonify({"error": "Invalid plan"}), 400

    plan = PRICING[plan_key]
    total_cents = plan["base_price_cents"] + (
        plan["per_employee_cents"] * employees
    )

    session = stripe.checkout.Session.create(
        mode="subscription",
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": plan["currency"],
                "product_data": {"name": plan["name"]},
                "unit_amount": total_cents,
                "recurring": {"interval": "month"}
            },
            "quantity": 1
        }],
        success_url=f"{BASE_URL}/billing/success",
        cancel_url=f"{BASE_URL}/billing/cancel",
        metadata={
            "plan": plan_key,
            "employees": employees
        }
    )

    return jsonify({"checkout_url": session.url})

# =========================
# Stripe Webhook
# =========================
@app.route("/billing/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    event = stripe.Webhook.construct_event(
        payload, sig_header, STRIPE_WEBHOOK_SECRET
    )

    if event["type"] == "checkout.session.completed":
        print("Checkout completed:", event["data"]["object"]["id"])

    return jsonify({"received": True})

# =========================
# Legal (Required)
# =========================
@app.route("/legal/terms")
def terms():
    return jsonify({"terms": "FreightPay Terms of Service"})

@app.route("/legal/privacy")
def privacy():
    return jsonify({"privacy": "FreightPay Privacy Policy"})

@app.route("/legal/refund")
def refund():
    return jsonify({"refund": "FreightPay Refund Policy"})

# =========================
# Root
# =========================
@app.route("/")
def index():
    return jsonify({
        "app": "FreightPay",
        "version": "v5-production",
        "status": "live"
    })

# =========================
# Entry
# =========================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

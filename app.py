# app.py
# FreightPay – Full Production Deployment v5
# Date: 2026-01-03
# Status: Production-ready (Stripe price_id based)

import os
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

from flask import Flask, request, jsonify
from flask_cors import CORS
import stripe

# =========================
# Database URL check (SAFE)
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")
print("DATABASE_URL_PRESENT =", bool(DATABASE_URL))
if DATABASE_URL:
    try:
        u = urlsplit(DATABASE_URL)
        netloc = u.netloc
        if "@" in netloc and ":" in netloc.split("@")[0]:
            userinfo, hostinfo = netloc.split("@", 1)
            user = userinfo.split(":", 1)[0]
            netloc = f"{user}:****@{hostinfo}"
        print(
            "DATABASE_URL_VALUE_MASKED =",
            urlunsplit((u.scheme, netloc, u.path, u.query, u.fragment)),
        )
    except Exception:
        print("DATABASE_URL_VALUE_MASKED = (mask failed)")

# =========================
# App Initialization
# =========================
app = Flask(__name__)
CORS(app)

# =========================
# Environment Variables
# =========================
APP_ENV = os.getenv("APP_ENV", "production")
BASE_URL = os.getenv("BASE_URL", "https://api.ledgerhaul.com")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Saved Stripe Price IDs (from your Render env screenshot)
STRIPE_BOOKKEEPING_PRICE_ID = os.getenv("STRIPE_BOOKKEEPING_PRICE_ID")
STRIPE_COMBO_PRICE_ID = os.getenv("STRIPE_COMBO_PRICE_ID")
STRIPE_COMBO_PER_EMPLOYEE_PRICE_ID = os.getenv("STRIPE_COMBO_PER_EMPLOYEE_PRICE_ID")
STRIPE_PAYROLL_PRICE_ID = os.getenv("STRIPE_PAYROLL_PRICE_ID")
STRIPE_PAYROLL_PER_EMPLOYEE_PRICE_ID = os.getenv("STRIPE_PAYROLL_PER_EMPLOYEE_PRICE_ID")

if not STRIPE_SECRET_KEY or not STRIPE_WEBHOOK_SECRET:
    raise RuntimeError("Missing STRIPE_SECRET_KEY or STRIPE_WEBHOOK_SECRET")

stripe.api_key = STRIPE_SECRET_KEY


def _require(value: str | None, key: str) -> str:
    if not value or not value.strip():
        raise RuntimeError(f"Missing required env var: {key}")
    return value.strip()


def _safe_int(v, default=0) -> int:
    try:
        i = int(v)
        return i if i >= 0 else default
    except Exception:
        return default


# =========================
# Pricing Map (Price IDs)
# =========================
# Combo: base + per-employee
# Payroll only: base + per-employee
# Bookkeeping only: base only
PRICING = {
    "combo": {
        "name": "Payroll + Bookkeeping",
        "base_price_id": STRIPE_COMBO_PRICE_ID,
        "per_employee_price_id": STRIPE_COMBO_PER_EMPLOYEE_PRICE_ID,
    },
    "payroll_only": {
        "name": "Payroll Only",
        "base_price_id": STRIPE_PAYROLL_PRICE_ID,
        "per_employee_price_id": STRIPE_PAYROLL_PER_EMPLOYEE_PRICE_ID,
    },
    "bookkeeping_only": {
        "name": "Bookkeeping Only",
        "base_price_id": STRIPE_BOOKKEEPING_PRICE_ID,
        "per_employee_price_id": None,
    },
}

# Validate required env vars for plans you intend to sell
_require(PRICING["combo"]["base_price_id"], "STRIPE_COMBO_PRICE_ID")
_require(PRICING["combo"]["per_employee_price_id"], "STRIPE_COMBO_PER_EMPLOYEE_PRICE_ID")
_require(PRICING["payroll_only"]["base_price_id"], "STRIPE_PAYROLL_PRICE_ID")
_require(PRICING["payroll_only"]["per_employee_price_id"], "STRIPE_PAYROLL_PER_EMPLOYEE_PRICE_ID")
_require(PRICING["bookkeeping_only"]["base_price_id"], "STRIPE_BOOKKEEPING_PRICE_ID")


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
# Stripe Checkout (Subscription)
# =========================
@app.route("/billing/checkout", methods=["POST"])
def create_checkout():
    data = request.json or {}
    plan_key = (data.get("plan") or "").strip()
    employees = _safe_int(data.get("employees", 0), default=0)

    if plan_key not in PRICING:
        return jsonify({"error": "Invalid plan"}), 400

    plan = PRICING[plan_key]
    base_price_id = _require(plan["base_price_id"], f"{plan_key}.base_price_id")

    line_items = [
        {"price": base_price_id, "quantity": 1}
    ]

    # Add per-employee line item if plan uses it and employees > 0
    per_emp_price_id = plan.get("per_employee_price_id")
    if per_emp_price_id and employees > 0:
        line_items.append({
            "price": _require(per_emp_price_id, f"{plan_key}.per_employee_price_id"),
            "quantity": employees
        })

    session = stripe.checkout.Session.create(
        mode="subscription",
        payment_method_types=["card"],
        line_items=line_items,
        success_url=f"{BASE_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{BASE_URL}/billing/cancel",
        metadata={
            "plan": plan_key,
            "employees": str(employees),
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

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception:
        return jsonify({"error": "Webhook signature verification failed"}), 400

    event_type = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}

    if event_type == "checkout.session.completed":
        print("checkout.session.completed:", obj.get("id"))

    elif event_type == "customer.subscription.created":
        print("customer.subscription.created:", obj.get("id"))

    elif event_type == "customer.subscription.updated":
        print("customer.subscription.updated:", obj.get("id"))

    elif event_type == "customer.subscription.deleted":
        print("customer.subscription.deleted:", obj.get("id"))

    elif event_type == "invoice.payment_failed":
        print("invoice.payment_failed:", obj.get("id"))

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

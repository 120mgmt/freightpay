# app.py — FULL, RESTORED, PRODUCTION-SAFE
# This file is COMPLETE. Nothing omitted. No placeholders.
# Compatible with Render + Gunicorn.
# Assumes project root layout exactly as shown (NO src/ folder).

from __future__ import annotations

import os
from flask import Flask, jsonify

# ======================
# Blueprint Imports
# ======================
# These MUST exist exactly as named in your repo

from payroll.routes.payroll_routes import payroll_bp
from billing.checkout import billing_bp
from billing.customer_portal import portal_bp
from billing.webhooks import webhook_bp


# ======================
# App Factory
# ======================
def create_app() -> Flask:
    app = Flask(__name__)

    # ------------------
    # Core Config
    # ------------------
    app.config["JSON_SORT_KEYS"] = False

    # ------------------
    # Health Check (Render requires this)
    # ------------------
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    # ------------------
    # Blueprint Registry
    # ------------------
    # Order matters: webhooks last
    app.register_blueprint(payroll_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(webhook_bp)

    return app


# ======================
# Gunicorn Entrypoint
# ======================
app = create_app()


# ======================
# Local Dev Only
# (Render ignores this block)
# ======================
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

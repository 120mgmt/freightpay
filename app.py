# app.py — FULL, RESTORED, PRODUCTION-SAFE

from __future__ import annotations

import os
from flask import Flask, jsonify

# Blueprint imports (must exist exactly as named)
from billing.checkout import billing_bp
from billing.customer_portal import portal_bp
from billing.webhooks import webhook_bp
from payroll.routes.payroll_routes import payroll_bp
from freightpay.legal.routes.legal_routes import legal_bp


# Config
from config import get_config


def create_app() -> Flask:
    app = Flask(__name__)

    # Load config
    app.config.from_object(get_config())

    # Core config
    app.config["JSON_SORT_KEYS"] = False

    # Health check (Render requires this)
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    # Blueprint registry (order matters: webhooks last)
    app.register_blueprint(payroll_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(webhook_bp)
    app.register_blueprint(legal_bp)
    return app


# Gunicorn entrypoint
app = create_app()

# Local dev only (ignored by Render)
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

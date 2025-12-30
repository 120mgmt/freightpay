# freightpay/app.py

from flask import Flask, jsonify, request

# Blueprint imports (must exist exactly as named)
from billing.checkout import billing_bp
from billing.customer_portal import portal_bp
from billing.webhooks import webhook_bp
from payroll.routes.payroll_routes import payroll_bp
from legal.routes.legal_routes import legal_bp
from bookkeeping.routes import bookkeeping_bp
from integrations.gusto.oauth import gusto_bp

# Config
from config import get_config

# Legal enforcement
from utils.legal_guard import enforce_legal_acceptance


def create_app() -> Flask:
    app = Flask(__name__)

    # Load config
    app.config.from_object(get_config())
    app.config["JSON_SORT_KEYS"] = False

    # Health check (Render requires this)
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    # Enforce legal acceptance globally (runs before every request)
    @app.before_request
    def legal_guard():
        # Never block health / static / legal pages / webhooks
        path = request.path or ""
        if path.startswith("/health"):
            return None
        if path.startswith("/legal"):
            return None
        if path.startswith("/static"):
            return None
        if path.startswith("/billing/webhook") or path.startswith("/webhook"):
            return None

        return enforce_legal_acceptance()

    # Blueprint registry (order matters: webhooks last)
    app.register_blueprint(payroll_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(legal_bp)
    app.register_blueprint(bookkeeping_bp)
    app.register_blueprint(gusto_bp)

    # Optional: billing store blueprint (if present)
    from billing.store import store_bp
    app.register_blueprint(store_bp)

    app.register_blueprint(webhook_bp)

    return app


# Gunicorn entrypoint
app = create_app()

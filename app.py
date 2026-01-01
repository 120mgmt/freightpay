# freightpay/app.py
# V5 PRODUCTION – FULL DEPLOYMENT ENTRYPOINT

from flask import Flask, jsonify, request

# Blueprints
from billing.checkout import billing_bp
from billing.customer_portal import portal_bp
from billing.webhooks import webhook_bp
from payroll.routes.payroll_routes import payroll_bp
from legal.routes.legal_routes import legal_bp
from bookkeeping.routes import bookkeeping_bp
from integrations.gusto.oauth import gusto_bp
from users.routes import users_bp

# Core config & DB
from config import get_config
from utils.database import init_db

# Guards
from utils.legal_guard import enforce_legal_acceptance


def create_app() -> Flask:
    app = Flask(__name__)

    # -----------------------
    # CONFIG
    # -----------------------
    app.config.from_object(get_config())
    app.config["JSON_SORT_KEYS"] = False

    # -----------------------
    # DATABASE LIFECYCLE
    # -----------------------
    init_db(app)

    # -----------------------
    # ROOT / HEALTH
    # -----------------------
    @app.route("/", methods=["GET"])
    def index():
        return jsonify(
            {
                "app": "FreightPay",
                "status": "live",
                "health": "/health",
                "legal": {
                    "terms": "/legal/terms",
                    "privacy": "/legal/privacy",
                    "refund": "/legal/refund",
                    "accept": "/legal/accept",
                },
            }
        ), 200

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    # -----------------------
    # GLOBAL LEGAL ENFORCEMENT
    # -----------------------
    @app.before_request
    def legal_guard():
        path = request.path or ""

        if (
            path == "/"
            or path.startswith("/health")
            or path.startswith("/legal")
            or path.startswith("/static")
            or path.startswith("/billing/webhook")
            or path.startswith("/webhook")
            or request.method == "OPTIONS"
        ):
            return None

        return enforce_legal_acceptance()

    # -----------------------
    # BLUEPRINT REGISTRATION
    # -----------------------
    app.register_blueprint(users_bp)
    app.register_blueprint(payroll_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(legal_bp)
    app.register_blueprint(bookkeeping_bp)
    app.register_blueprint(gusto_bp)

    # Billing store (subscriptions / status)
    from billing.store import store_bp
    app.register_blueprint(store_bp)

    # Stripe webhooks MUST be last
    app.register_blueprint(webhook_bp)

    return app


# -----------------------
# GUNICORN ENTRYPOINT
# -----------------------
app = create_app()

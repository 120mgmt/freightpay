# freightpay/__init__.py
# Purpose: App factory wiring – register legal + enforce acceptance (deployment)
# Status: Full deployment – production v5
# Date: 2026-01-01

from flask import Flask

from utils.database import init_db
from freightpay.legal import register_legal
from freightpay.app_factory_hooks import apply_legal_enforcement


def create_app() -> Flask:
    app = Flask(__name__)

    # Core config (env-driven)
    app.config.from_object("config.settings")

    # Database
    init_db(app)

    # Register blueprints (order matters)
    register_legal(app)

    # Enforce legal acceptance on protected routes
    apply_legal_enforcement(app)

    return app

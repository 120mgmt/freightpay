# freightpay/__init__.py
# Purpose: Application factory – full production wiring
# Status: Full deployment – production v5
# Date: 2026-01-01

from flask import Flask

from db import init_db
from legal import register_legal
from app_factory_hooks import apply_legal_enforcement
from app_factory_cli import register_app_cli


def create_app() -> Flask:
    app = Flask(__name__)

    # Core configuration (env-driven, production)
    app.config.from_object("config.settings")

    # Database init
    init_db(app)

    # Register legal routes (Terms / Privacy / Refund / Acceptance)
    register_legal(app)

    # Register CLI commands (seed, etc.)
    register_app_cli(app)

    # Enforce legal acceptance on protected routes
    apply_legal_enforcement(app)

    return app


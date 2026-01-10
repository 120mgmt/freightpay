# freightpay/__init__.py
# Application factory – production v5

from flask import Flask

from db import init_db
from legal import register_legal
from app_factory_hooks import apply_legal_enforcement
from app_factory_cli import register_app_cli


def create_app() -> Flask:
    app = Flask(__name__)

    # Core configuration
    app.config.from_object("config")

    # Database
    init_db(app)

    # Legal routes
    register_legal(app)

    # CLI commands
    register_app_cli(app)

    # Legal enforcement
    apply_legal_enforcement(app)

    return app





# freightpay/app_factory_cli.py
# Purpose: Attach CLI commands to the app (single entry path: app.py)
# Status: Full deployment – production v5
# Date: 2026-01-01

from flask import Flask

from cli import register_cli


def register_app_cli(app: Flask) -> None:
    """
    Called from app.py after blueprints are registered. Attaches CLI commands.
    """
    register_cli(app)

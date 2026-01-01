# freightpay/app_factory_cli.py
# Purpose: Attach CLI commands to app factory (deployment)
# Status: Full deployment – production v5
# Date: 2026-01-01

from flask import Flask

from freightpay.cli import register_cli


def register_app_cli(app: Flask) -> None:
    """
    Called from create_app() to attach CLI commands.
    """
    register_cli(app)

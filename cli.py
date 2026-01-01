# freightpay/cli.py
# Purpose: Register production CLI commands (seed, health checks)
# Status: Full deployment – production v5
# Date: 2026-01-01

from __future__ import annotations

import click
from flask import Flask

from freightpay.seed import run_seeds


def register_cli(app: Flask) -> None:
    @app.cli.command("seed")
    def seed_command():
        """Run production seed tasks"""
        run_seeds()
        click.echo("Seed completed successfully.")

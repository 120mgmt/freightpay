# File: sitecustomize.py
# Purpose: Enterprise import stabilizer for LedgerHaul runtime environments
# Ensures project root is always on PYTHONPATH for CI, Gunicorn, Flask CLI, pytest
# Status: Production hardened
# Date: 2026-03-05

from __future__ import annotations

import os
import sys
from pathlib import Path


def _resolve_project_root() -> str:
    """
    Determine the absolute project root containing app.py.
    Works for:
    - Render (gunicorn wsgi:app)
    - GitHub Actions CI
    - pytest
    - Flask CLI migrations
    """
    current = Path(__file__).resolve()

    # walk up directories until app.py is found
    for parent in [current] + list(current.parents):
        if (parent / "app.py").exists():
            return str(parent)

    # fallback
    return str(current.parent)


def _ensure_path() -> None:
    root = _resolve_project_root()

    if root not in sys.path:
        sys.path.insert(0, root)


def _configure_runtime_env() -> None:
    """
    Safe defaults for CI environments that may not provide full env config.
    Prevents early import crashes during static analysis tools.
    """
    os.environ.setdefault("APP_ENV", "testing")

    # Database is required by app.py during import
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+psycopg://ledgerhaul:ledgerhaul@localhost:5432/ledgerhaul_ci",
    )


def initialize() -> None:
    _ensure_path()
    _configure_runtime_env()


initialize()

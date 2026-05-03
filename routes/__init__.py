# routes/__init__.py — package export for route blueprints (app.py imports from routes.* submodules)

from __future__ import annotations

from routes.auth_routes import auth_bp
from routes.reporting import reporting_bp
from routes.reconciliation import reconciliation_bp

__all__ = ["auth_bp", "reporting_bp", "reconciliation_bp"]

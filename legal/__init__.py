# freightpay/legal/__init__.py
# Purpose: Register legal blueprints for production deployment
# Status: Full deployment – production v5
# Date: 2026-01-01

from freightpay.legal.routes import legal_bp
from freightpay.legal.routes_acceptance import legal_acceptance_bp


def register_legal(app):
    """
    Called from app factory to register all legal routes.
    """
    app.register_blueprint(legal_bp)
    app.register_blueprint(legal_acceptance_bp)

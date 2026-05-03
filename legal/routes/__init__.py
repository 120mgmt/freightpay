# legal/routes/__init__.py — single entrypoint for legal blueprints (legal_bp: templates + /accept)

from __future__ import annotations

from legal.routes.legal_routes import legal_bp

__all__ = ["legal_bp"]

# File: utils/legal_guard.py
# Purpose: Enforce TOS/Privacy acceptance for authenticated users (JWT-Extended)
# Status: Production-ready
# Date: 2026-01-24

from __future__ import annotations

from typing import Optional, Any

from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from models.user import User


def _safe_get_current_user() -> Optional[Any]:
    """
    Resolve authenticated user using Flask-JWT-Extended.
    Optional JWT verification so public routes don't fail.
    """
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        if not identity:
            return None

        # We set identity as a dict in routes/auth_routes.py
        # identity = {"user_id": ..., "company_id": ..., "role": ...}
        user_id = None
        if isinstance(identity, dict):
            user_id = identity.get("user_id")
        else:
            user_id = identity

        if user_id is None:
            return None

        return User.query.get(user_id)
    except Exception:
        return None


def enforce_legal_acceptance():
    """
    Global legal enforcement guard. Use via @app.before_request.

    Rules:
    - Always allow health, legal docs, auth endpoints, static assets, OPTIONS
    - Allow unauthenticated/public users
    - Block authenticated users who have not accepted TOS + Privacy
    """

    path = (request.path or "").strip()

    # Always-allowed routes
    if (
        path == "/"
        or path == "/health"
        or path.startswith("/legal/")
        or path.startswith("/static/")
        or path.startswith("/auth/")          # allow register/login/accept-legal
        or path.startswith("/billing/webhooks")
        or path.startswith("/webhook")
        or request.method == "OPTIONS"
    ):
        return None

    user = _safe_get_current_user()

    # Public / unauthenticated access is allowed
    if user is None:
        return None

    accepted_tos = bool(getattr(user, "accepted_tos", False))
    accepted_privacy = bool(getattr(user, "accepted_privacy", False))

    if accepted_tos and accepted_privacy:
        return None

    return (
        jsonify(
            {
                "error": "LEGAL_NOT_ACCEPTED",
                "message": "You must accept the Terms of Service and Privacy Policy to continue.",
                "required": {"tos": True, "privacy": True},
                "docs": {
                    "terms": "/legal/terms",
                    "privacy": "/legal/privacy",
                    "refund": "/legal/refund",
                },
                "next": "/auth/accept-legal",
            }
        ),
        403,
    )

# utils/legal_guard.py

from __future__ import annotations

from flask import jsonify, request
from typing import Any, Optional


def _safe_get_current_user() -> Optional[Any]:
    """
    Attempts to resolve the authenticated user.
    Fails safely if auth is not wired yet.
    """
    try:
        from utils.auth import get_current_user  # must exist if auth is enabled
        return get_current_user()
    except Exception:
        return None


def enforce_legal_acceptance():
    """
    Global legal enforcement guard.
    Used via @app.before_request.

    Rules:
    - Always allow health, legal docs, static assets, OPTIONS
    - Allow unauthenticated/public users
    - Block authenticated users who have not accepted TOS + Privacy
    """

    path = request.path or ""

    # Always-allowed routes
    if (
        path == "/health"
        or path == "/legal/terms"
        or path == "/legal/privacy"
        or path == "/legal/accept"
        or path.startswith("/static/")
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
                "required": {
                    "tos": True,
                    "privacy": True
                },
                "docs": {
                    "terms": "/legal/terms",
                    "privacy": "/legal/privacy"
                },
            }
        ),
        403,
    )

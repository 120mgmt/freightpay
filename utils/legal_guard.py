# utils/legal_guard.py

from __future__ import annotations

from flask import jsonify, request
from typing import Any, Optional


def _safe_get_current_user() -> Optional[Any]:
    """
    Tries to resolve the currently authenticated user without hard-failing
    if auth wiring isn't present yet.
    """
    try:
        # If you have get_current_user implemented in utils/auth.py
        from utils.auth import get_current_user  # type: ignore
        return get_current_user()
    except Exception:
        return None


def enforce_legal_acceptance():
    """
    Global guard enforced via @app.before_request.
    - Always allow: health + legal docs endpoints + static + OPTIONS
    - If user is not authenticated/unknown: allow (do not block public access)
    - If user is authenticated but hasn't accepted: block with 403 JSON
    """

    path = request.path or ""

    # Always-allow routes (prevents "blank page" on docs + keeps Render health happy)
    if (
        path == "/health"
        or path == "/legal/terms"
        or path == "/legal/privacy"
        or path.startswith("/static/")
        or request.method == "OPTIONS"
    ):
        return None

    # Allow the accept endpoint itself; it will be protected by @require_auth
    if path == "/legal/accept":
        return None

    user = _safe_get_current_user()

    # If we can't determine the user (public/unauthenticated), don't block.
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
                "docs": {"terms": "/legal/terms", "privacy": "/legal/privacy"},
            }
        ),
        403,
    )

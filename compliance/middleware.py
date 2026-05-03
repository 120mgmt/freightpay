# compliance/middleware.py
# Global request enforcement for legal acceptance (backend-only, no frontend dependency)

from flask import request, jsonify
from flask_login import current_user

from compliance.models import LegalDocument, UserLegalAcceptance


EXEMPT_PATH_PREFIXES = (
    "/auth",
    "/login",
    "/logout",
    "/health",
    "/static",
    "/compliance",   # allow access to compliance endpoints themselves
)


def _is_exempt_path(path: str) -> bool:
    return any(path.startswith(p) for p in EXEMPT_PATH_PREFIXES)


def _active_doc(doc_key: str):
    return (
        LegalDocument.query
        .filter_by(doc_key=doc_key, is_active=True)
        .order_by(LegalDocument.effective_at.desc())
        .first()
    )


def _accepted(user_id: int, doc_key: str, version: str) -> bool:
    return (
        UserLegalAcceptance.query
        .filter_by(
            user_id=user_id,
            doc_key=doc_key,
            version=version,
            accepted=True,
        )
        .first()
        is not None
    )


def enforce_legal_acceptance():
    """
    Register as app.before_request.
    Blocks authenticated users from accessing protected routes
    until active Terms + Privacy are accepted.
    """
    path = request.path or ""
    if _is_exempt_path(path):
        return None

    if not current_user.is_authenticated:
        return None

    missing = []
    for key in ("terms", "privacy"):
        doc = _active_doc(key)
        if not doc:
            missing.append({"doc_key": key, "reason": "no_active_document"})
            continue
        if not _accepted(current_user.id, key, doc.version):
            missing.append({"doc_key": key, "required_version": doc.version})

    if missing:
        return jsonify({
            "error": "legal_acceptance_required",
            "missing": missing
        }), 403

    return None

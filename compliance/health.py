# File: compliance/health.py
# Purpose: Compliance health check endpoint (JWT-only)
# Verifies: active legal docs seeded
# Date: 2026-01-26

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from compliance.models import LegalDocument

compliance_health_bp = Blueprint("compliance_health", __name__, url_prefix="/compliance")


def _active(doc_key: str):
    return (
        LegalDocument.query
        .filter_by(doc_key=doc_key, is_active=True)
        .order_by(LegalDocument.effective_at.desc())
        .first()
    )


@compliance_health_bp.route("/health", methods=["GET"])
@jwt_required()
def compliance_health():
    terms = _active("terms")
    privacy = _active("privacy")

    status = {
        "terms": {
            "active": bool(terms),
            "version": terms.version if terms else None,
            "effective_at": terms.effective_at.isoformat() if terms else None,
        },
        "privacy": {
            "active": bool(privacy),
            "version": privacy.version if privacy else None,
            "effective_at": privacy.effective_at.isoformat() if privacy else None,
        },
        "ready": bool(terms and privacy),
    }

    return jsonify(status), (200 if status["ready"] else 503)

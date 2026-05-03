# compliance/admin_routes.py
# Admin-only compliance endpoints (JWT-only, LedgerHaul)
# Date: 2026-01-26

from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from db import db
from compliance.models import LegalDocument, UserLegalAcceptance

admin_compliance_bp = Blueprint("admin_compliance", __name__, url_prefix="/admin/compliance")


def _is_admin_identity(identity: Any) -> bool:
    """
    LedgerHaul JWT identity is expected to be a dict like:
      {"user_id":..., "company_id":..., "role":"admin"|...}
    """
    if not identity or not isinstance(identity, dict):
        return False
    return (identity.get("role") or "").strip().lower() == "admin"


@admin_compliance_bp.before_request
@jwt_required()
def _guard_admin():
    ident = get_jwt_identity()
    if not _is_admin_identity(ident):
        return jsonify({"error": "forbidden"}), 403
    return None


@admin_compliance_bp.route("/documents", methods=["GET"])
def list_documents():
    docs = (
        LegalDocument.query
        .order_by(LegalDocument.doc_key.asc(), LegalDocument.effective_at.desc())
        .all()
    )
    return jsonify(
        {
            "documents": [
                {
                    "id": d.id,
                    "doc_key": d.doc_key,
                    "version": d.version,
                    "checksum": d.checksum,
                    "effective_at": d.effective_at.isoformat() if d.effective_at else None,
                    "is_active": bool(d.is_active),
                }
                for d in docs
            ]
        }
    ), 200


@admin_compliance_bp.route("/documents", methods=["POST"])
def create_document():
    """
    Create + optionally activate a new legal document version.

    Body:
      {
        "doc_key": "terms" | "privacy" | "refund",
        "version": "2026-01-26",
        "checksum": "optional",
        "effective_at": "2026-01-26T00:00:00Z",
        "activate": true
      }
    """
    data = request.get_json(force=True, silent=False) or {}
    doc_key = (data.get("doc_key") or "").strip()
    version = (data.get("version") or "").strip()
    checksum = (data.get("checksum") or "").strip() or None
    activate = bool(data.get("activate", True))

    if not doc_key or not version:
        return jsonify({"error": "invalid_payload"}), 400

    effective_at_raw = (data.get("effective_at") or "").strip()
    if effective_at_raw:
        try:
            effective_at = datetime.fromisoformat(effective_at_raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return jsonify({"error": "invalid_effective_at"}), 400
    else:
        effective_at = datetime.utcnow()

    if activate:
        LegalDocument.query.filter_by(doc_key=doc_key, is_active=True).update({"is_active": False})

    doc = LegalDocument(
        doc_key=doc_key,
        version=version,
        checksum=checksum,
        effective_at=effective_at,
        is_active=activate,
    )
    db.session.add(doc)
    db.session.commit()

    return jsonify({"status": "created", "id": doc.id}), 201


@admin_compliance_bp.route("/acceptances", methods=["GET"])
def list_acceptances():
    """
    Query acceptances by doc_key/version/user_id
    """
    doc_key = (request.args.get("doc_key") or "").strip() or None
    version = (request.args.get("version") or "").strip() or None
    user_id = request.args.get("user_id", type=int)

    q = UserLegalAcceptance.query
    if doc_key:
        q = q.filter_by(doc_key=doc_key)
    if version:
        q = q.filter_by(version=version)
    if user_id:
        q = q.filter_by(user_id=user_id)

    rows = q.order_by(UserLegalAcceptance.id.desc()).limit(500).all()

    return jsonify(
        {
            "acceptances": [
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "doc_key": r.doc_key,
                    "version": r.version,
                    "accepted": bool(r.accepted),
                    "accepted_at": r.accepted_at.isoformat() if r.accepted_at else None,
                }
                for r in rows
            ]
        }
    ), 200

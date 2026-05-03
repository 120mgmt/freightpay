# compliance/routes.py
# Backend endpoints + enforcement helpers for legal document acceptance (versioned)
# LedgerHaul wiring: uses db from db.py (Flask-SQLAlchemy instance)

from datetime import datetime
from functools import wraps

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import db
from compliance.models import LegalDocument, UserLegalAcceptance

def _get_current_user_id() -> int | None:
    identity = get_jwt_identity()
    if isinstance(identity, dict):
        return identity.get("user_id")
    return None


compliance_bp = Blueprint("compliance", __name__, url_prefix="/compliance")


def _active_doc(doc_key: str) -> LegalDocument | None:
    return (
        LegalDocument.query
        .filter_by(doc_key=doc_key, is_active=True)
        .order_by(LegalDocument.effective_at.desc())
        .first()
    )


def _user_has_accepted(user_id: int, doc_key: str, version: str) -> bool:
    rec = (
        UserLegalAcceptance.query
        .filter_by(user_id=user_id, doc_key=doc_key, version=version, accepted=True)
        .first()
    )
    return rec is not None


def require_legal_acceptance(doc_keys: list[str] | None = None):
    """
    Use on protected routes that require current active legal acceptance.
    Default requires both terms + privacy.
    """
    if not doc_keys:
        doc_keys = ["terms", "privacy"]

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user_id = _get_current_user_id()
            if not user_id:
                return jsonify({"error": "authentication_required"}), 401

            missing = []
            for key in doc_keys:
                doc = _active_doc(key)
                if not doc:
                    missing.append({"doc_key": key, "reason": "no_active_document"})
                    continue
                if not _user_has_accepted(_get_current_user_id(), key, doc.version):
                    missing.append({"doc_key": key, "required_version": doc.version})

            if missing:
                return jsonify({
                    "error": "legal_acceptance_required",
                    "missing": missing
                }), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator


@compliance_bp.route("/legal/active", methods=["GET"])
@jwt_required()
def get_active_legal_versions():
    keys = request.args.getlist("doc_key") or ["terms", "privacy"]
    payload = []
    for key in keys:
        doc = _active_doc(key)
        payload.append({
            "doc_key": key,
            "version": doc.version if doc else None,
            "effective_at": doc.effective_at.isoformat() if doc else None,
            "checksum": doc.checksum if doc else None,
            "is_active": bool(doc),
        })
    return jsonify({"documents": payload}), 200


@compliance_bp.route("/legal/accept", methods=["POST"])
@jwt_required()
def accept_legal():
    """
    Body:
      {
        "accept": [
          {"doc_key":"terms","version":"2026-01-25"},
          {"doc_key":"privacy","version":"2026-01-25"}
        ]
      }
    """
    data = request.get_json(force=True)
    items = data.get("accept") or []
    if not isinstance(items, list) or not items:
        return jsonify({"error": "invalid_payload"}), 400

    accepted = []
    for item in items:
        doc_key = (item.get("doc_key") or "").strip()
        version = (item.get("version") or "").strip()
        if not doc_key or not version:
            continue

        # only allow acceptance of an active document version (prevents stale acceptance)
        doc = _active_doc(doc_key)
        if not doc or doc.version != version:
            continue

        rec = (
            UserLegalAcceptance.query
            .filter_by(user_id=_get_current_user_id(), doc_key=doc_key, version=version)
            .first()
        )
        if not rec:
            rec = UserLegalAcceptance(
                user_id=_get_current_user_id(),
                doc_key=doc_key,
                version=version,
                accepted=True,
                accepted_at=datetime.utcnow(),
            )
            db.session.add(rec)
        else:
            rec.accepted = True
            rec.accepted_at = datetime.utcnow()

        accepted.append({"doc_key": doc_key, "version": version})

    if not accepted:
        return jsonify({"error": "no_valid_documents_to_accept"}), 400

    db.session.commit()
    return jsonify({"status": "accepted", "accepted": accepted}), 200


@compliance_bp.route("/legal/status", methods=["GET"])
@jwt_required()
def legal_status():
    """
    Returns whether the current user has accepted the active versions.
    """
    keys = request.args.getlist("doc_key") or ["terms", "privacy"]
    results = []

    for key in keys:
        doc = _active_doc(key)
        if not doc:
            results.append({
                "doc_key": key,
                "active_version": None,
                "accepted": False,
                "accepted_at": None,
                "reason": "no_active_document",
            })
            continue

        rec = (
            UserLegalAcceptance.query
            .filter_by(user_id=_get_current_user_id(), doc_key=key, version=doc.version)
            .first()
        )
        results.append({
            "doc_key": key,
            "active_version": doc.version,
            "accepted": bool(rec and rec.accepted),
            "accepted_at": rec.accepted_at.isoformat() if rec and rec.accepted_at else None,
        })

    return jsonify({"status": results}), 200

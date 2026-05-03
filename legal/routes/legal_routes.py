# legal/routes/legal_routes.py

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request, render_template
from sqlalchemy.orm import Session

from models import User
from legal.service import record_full_acceptance_bundle
from utils.database import get_db
from utils.auth import require_auth

legal_bp = Blueprint("legal", __name__, url_prefix="/legal")


@legal_bp.get("/terms")
def get_terms():
    return render_template("legal/terms_of_service.html"), 200


@legal_bp.get("/privacy")
def get_privacy():
    return render_template("legal/privacy.html"), 200


@legal_bp.get("/refund")
def get_refund():
    return render_template("legal/refund.html"), 200


@legal_bp.post("/accept")
@require_auth
def accept_legal(user: User, **kwargs):
    """
    Body:
      { "accept_tos": true, "accept_privacy": true, "version": "1.0" }
    Persists one LegalAcceptance row (terms_version, privacy_version, refund_version) via canonical legal.service.
    """
    data = request.get_json(silent=True) or {}
    tos = data.get("accept_tos")
    privacy = data.get("accept_privacy")

    if tos is not True or privacy is not True:
        return jsonify({"error": "BOTH_TOS_AND_PRIVACY_REQUIRED"}), 400

    session: Session = get_db()
    ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
    user_agent = request.headers.get("User-Agent")

    record_full_acceptance_bundle(
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        session=session,
    )

    # Keep User flags in sync (columns exist on User model)
    user.accepted_tos = True
    user.accepted_privacy = True
    user.accepted_refund = True
    user.legal_accepted_at = datetime.utcnow()
    session.commit()

    return jsonify({"status": "accepted"}), 200

# legal/routes/legal_routes.py

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request, render_template
from sqlalchemy.orm import Session

from models import User, LegalAcceptance
from utils.database import get_db
from utils.auth import require_auth

legal_bp = Blueprint("legal", __name__, url_prefix="/legal")


@legal_bp.get("/terms")
def get_terms():
    return render_template("legal/terms.html"), 200


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
    """
    data = request.get_json(silent=True) or {}
    tos = data.get("accept_tos")
    privacy = data.get("accept_privacy")
    version = (data.get("version") or "").strip() or None

    if tos is not True or privacy is not True:
        return jsonify({"error": "BOTH_TOS_AND_PRIVACY_REQUIRED"}), 400

    db: Session = get_db()

    # Persist flags on user (these columns must exist on User model)
    user.accepted_tos = True
    user.accepted_privacy = True
    user.legal_accepted_at = datetime.utcnow()

    # Audit log rows
    db.add(LegalAcceptance(user_id=user.id, document="tos", version=version))
    db.add(LegalAcceptance(user_id=user.id, document="privacy", version=version))

    db.commit()

    return jsonify({"status": "accepted"}), 200

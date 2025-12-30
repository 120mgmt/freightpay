from flask import Blueprint, jsonify, request, render_template
from sqlalchemy.orm import Session
from datetime import datetime

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
def accept_legal(user: User, db: Session = get_db()):
    data = request.json or {}
    tos = data.get("accept_tos")
    privacy = data.get("accept_privacy")

    if tos is not True or privacy is not True:
        return jsonify({"error": "Both TOS and Privacy must be accepted"}), 400

    user.accepted_tos = True
    user.accepted_privacy = True
    user.legal_accepted_at = datetime.utcnow()

    db.add(LegalAcceptance(user_id=user.id, document="tos"))
    db.add(LegalAcceptance(user_id=user.id, document="privacy"))
    db.commit()

    return jsonify({"status": "accepted"}), 200


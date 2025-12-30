from flask import Blueprint, jsonify, request
from sqlalchemy.orm import Session
from datetime import datetime
from freightpay.models import User, LegalAcceptance
from freightpay.utils.database import get_db
from freightpay.utils.auth import require_auth

legal_bp = Blueprint("legal", __name__, url_prefix="/legal")

@legal_bp.get("/terms")
def get_terms():
    return jsonify({
        "title": "Terms of Service",
        "version": "1.0",
        "content": "By using FreightPay, you agree to payroll processing, ACH transfers, and compliance requirements."
    })

@legal_bp.get("/privacy")
def get_privacy():
    return jsonify({
        "title": "Privacy Policy",
        "version": "1.0",
        "content": "FreightPay stores user data securely and never sells personal information."
    })

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

    return jsonify({"status": "accepted"})

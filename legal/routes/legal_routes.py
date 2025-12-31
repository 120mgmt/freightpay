from flask import Blueprint, jsonify, request
from datetime import datetime

legal_bp = Blueprint("legal", __name__, url_prefix="/legal")


@legal_bp.get("/terms")
def get_terms():
    return jsonify(
        {
            "title": "Terms of Service",
            "version": "1.0",
            "content": "By using FreightPay, you agree to payroll processing, ACH transfers, compliance requirements, and ACH authorization."
        }
    ), 200


@legal_bp.get("/privacy")
def get_privacy():
    return jsonify(
        {
            "title": "Privacy Policy",
            "version": "1.0",
            "content": "FreightPay stores user data securely, uses encryption, and does not sell personal information."
        }
    ), 200


@legal_bp.get("/refund")
def get_refund():
    return jsonify(
        {
            "title": "Refund Policy",
            "version": "1.0",
            "content": "All subscription fees are non-refundable once billing has occurred."
        }
    ), 200


@legal_bp.post("/accept")
def accept_legal():
    data = request.get_json(silent=True) or {}

    if data.get("accept_tos") is not True or data.get("accept_privacy") is not True:
        return jsonify(
            {
                "error": "Both Terms of Service and Privacy Policy must be accepted"
            }
        ), 400

    return jsonify(
        {
            "status": "accepted",
            "accepted_at": datetime.utcnow().isoformat()
        }
    ), 200


from flask import Blueprint, jsonify, request
billing_bp = Blueprint("billing", __name__)

@billing_bp.route("/invoice", methods=["POST"])
def create_invoice():
    data = request.json
    return jsonify({"status": "invoice_created", "data": data})

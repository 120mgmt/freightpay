from flask import Blueprint, request, jsonify
from payroll.engine import run_payroll

payroll_bp = Blueprint("payroll", __name__, url_prefix="/payroll")

@payroll_bp.route("/run", methods=["POST"])
def run_payroll_route():
    data = request.get_json(silent=True) or {}
    contractors = data.get("contractors", []) 
    results = run_payroll(contractors)
    return jsonify({"status": "ok", "results": results}), 200

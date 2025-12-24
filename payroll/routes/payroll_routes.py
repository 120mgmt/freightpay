from flask import Blueprint, request, jsonify

# RELATIVE import - required for production
from . .engine import run_payroll

payroll_bp = Blueprint("payroll", __name__)

@payroll_bp.route("/run", methods=["POST"])
def run_payroll_route():
    data = request.get_json(silent=True) or {}
    contractors = data.get("contractors", []) 
    
    results = run_payroll(contractors)

    return jsonify({
        "status": "ok",
        "results": results
    }), 200

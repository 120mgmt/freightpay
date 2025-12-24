# payroll/routes/payroll_routes.py

from flask import Blueprint, request, jsonify
from payroll.engine import run_payroll

#IMPORTANT:
# - B;ueprint name must be UNIQUE across the whole app
# - Do NOT set url_prefix here since app.py already sets url_prefix="/payroll"
payroll_bp = Blueprint("payroll_api", __name__)

@payroll_bp.route("/run")
def run_payroll_route():
    data = request.get_json(silent=True) or {}
    contractors = data.get("contractors", [])  or []
    
    results = run_payroll(contractors)
    
    return jsonify({
        "status": "ok",
        "results": results
    }), 200

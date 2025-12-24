# payroll/routes/payroll_routes.py

from flask import Blueprint, request, jsonify
from payroll.engine import run_payroll

# IMPORTANT:
# Do NOT put url_prefix here if you're also setting url_prefix when registering the blueprint in app.py
payroll_bp = Blueprint("payroll_api", __name__)

@payroll_bp.route("/run", methods=["POST"])
def run_payroll_route():
    data = request.get_json(force=True) or {}
    contractors = data.get("contractors", []) or []

    results = run_payroll(contractors)
    return jsonify({"status": "ok", "results": results}), 200

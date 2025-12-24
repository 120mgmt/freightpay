from flask import Blueprint, request, jsonify
from paroll.engine import run_payroll

payroll_bp = Blueprint("payroll", __name__, url_prefix="/payroll")


@payroll_bp.post("/run")
def payroll_run():
    data = request.get_json(silent=True) or {}
    result = run_payroll(data)
    return jsonify(result), 200

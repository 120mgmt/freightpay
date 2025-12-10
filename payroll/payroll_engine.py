
from flask import Blueprint, jsonify
from .pay_calculations import calculate_pay

payroll_bp = Blueprint("payroll", __name__)

@payroll_bp.route("/run", methods=["POST"])
def run_payroll():
    return jsonify({"payroll": "processed"})

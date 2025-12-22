from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# -----------------------
# Health check
# -----------------------
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "FreightPay running"}), 200


# -----------------------
# Payroll
# -----------------------
@app.route("/payroll/run", methods=["POST"])
def run_payroll():
    try:
        from payroll_engine import run_payroll
        data = request.json
        result = run_payroll(data)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------
# Contractor Pay
# -----------------------
@app.route("/payroll/contractor", methods=["POST"])
def contractor_pay():
    try:
        from contractor_pay import calculate_contractor_pay
        data = request.json
        result = calculate_contractor_pay(data)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------
# Taxes
# -----------------------
@app.route("/payroll/taxes", methods=["POST"])
def payroll_taxes():
    try:
        from taxes import calculate_taxes
        data = request.json
        result = calculate_taxes(data)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

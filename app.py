from flask import Flask, request, jsonify
import os

# Core modules (root-level files)
from payroll_engine import run_payroll
from contractor_pay import calculate_contractor_pay
from taxes import calculate_taxes
from deductions import calculate_deductions

app = Flask(__name__)

# -------------------------
# Health / Root
# -------------------------
@app.route("/", methods=["GET"])
def root():
    return jsonify({"status": "FreightPay running"}), 200


# -------------------------
# Payroll Endpoint
# -------------------------
@app.route("/payroll/run", methods=["POST"])
def payroll_run():
    data = request.json
    result = run_payroll(data)
    return jsonify(result), 200


# -------------------------
# Contractor Pay
# -------------------------
@app.route("/payroll/contractor", methods=["POST"])
def contractor_pay():
    data = request.json
    result = calculate_contractor_pay(data)
    return jsonify(result), 200


# -------------------------
# Taxes
# -------------------------
@app.route("/payroll/taxes", methods=["POST"])
def taxes():
    data = request.json
    result = calculate_taxes(data)
    return jsonify(result), 200


# -------------------------
# Deductions
# -------------------------
@app.route("/payroll/deductions", methods=["POST"])
def deductions():
    data = request.json
    result = calculate_deductions(data)
    return jsonify(result), 200


# -------------------------
# Render / Gunicorn entry
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

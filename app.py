from flask import Flask, request, jsonify
import os

# Payroll modules (already uploaded)
from payroll_engine import run_payroll
from contractor_pay import calculate_contractor_pay
from taxes import calculate_taxes

app = Flask(__name__)

# =========================
# Health / Status
# =========================
@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "FreightPay running",
        "services": ["payroll", "contractor_pay", "taxes"]
    }), 200


# =========================
# Payroll (Employees)
# =========================
@app.route("/payroll/run", methods=["POST"])
def payroll_run():
    data = request.get_json() or {}
    result = run_payroll(data)
    return jsonify(result), 200


# =========================
# Contractor Pay
# =========================
@app.route("/contractors/run", methods=["POST"])
def contractor_run():
    data = request.get_json() or {}

    gross = data.get("gross_amount", 0)
    platform_fee = data.get("platform_fee_rate", 0)

    result = calculate_contractor_pay(
        gross_amount=gross,
        platform_fee_rate=platform_fee
    )
    return jsonify(result), 200


# =========================
# Taxes
# =========================
@app.route("/taxes/calculate", methods=["POST"])
def taxes_run():
    data = request.get_json() or {}
    gross = data.get("gross_pay", 0)

    result = calculate_taxes(gross)
    return jsonify(result), 200


# =========================
# Render / Gunicorn
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

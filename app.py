from flask import Flask, request, jsonify
import os

# Core modules you already uploaded
from payroll_engine import run_payroll
from contractor_pay import calculate_contractor_pay
from taxes import calculate_taxes

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "FreightPay running"})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/pay/contractor", methods=["POST"])
def contractor_pay():
    data = request.get_json(force=True) or {}
    return jsonify(calculate_contractor_pay(data))

@app.route("/taxes/calculate", methods=["POST"])
def taxes_calc():
    data = request.get_json(force=True) or {}
    return jsonify(calculate_taxes(data))

@app.route("/payroll/run", methods=["POST"])
def payroll_run():
    data = request.get_json(force=True) or {}
    return jsonify(run_payroll(data))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

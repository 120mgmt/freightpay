
from flask import Flask, jsonify, request
from payroll.payroll_engine import run_payroll
from payroll.deductions import calculate_deductions
from payroll.contractor_pay import calculate_contractor_pay

app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "FreightPay running"})

@app.route("/payroll/run", methods=["POST"])
def payroll():
    data = request.json
    return jsonify(run_payroll(data))

if __name__ == "__main__":
    app.run()

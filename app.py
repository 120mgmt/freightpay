from flask import Flask, jsonify, request
import os

# ---- App init ----
app = Flask(__name__)

# ---- Health / root ----
@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "service": "payroll",
        "status": "FreightPay live"
    })

# ---- Bookkeeping ledger hook ----
# This records payroll results into the in-memory ledger
from bookkeeping.ledger import record_payroll_run, get_ledger

@app.route("/bookkeeping/record", methods=["POST"])
def record_bookkeeping():
    data = request.json or {}

    entry = record_payroll_run(
        pay_period=data.get("pay_period"),
        contractor_id=data.get("contractor_id"),
        gross=float(data.get("gross", 0)),
        reimbursements=float(data.get("reimbursements", 0)),
        deductions=float(data.get("deductions", 0)),
        net=float(data.get("net", 0)),
    )
    return jsonify(entry), 201

@app.route("/bookkeeping/ledger", methods=["GET"])
def view_ledger():
    return jsonify(get_ledger())

# ---- Run (Render / Gunicorn safe) ----
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


          

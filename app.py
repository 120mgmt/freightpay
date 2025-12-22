from flask import Flask, request, jsonify
from payroll.engine import run_payroll
from payroll.export_csv import settlements_to_csv

app = Flask(__name__)

@app.get("/")
def health():
    return jsonify({
        "status": "FreightPay live",
        "service": "payroll"
    })

@app.post("/api/payroll/run")
def run_payroll_api():
    payload = request.get_json(force=True) or {}
    drivers = payload.get("drivers", [])
    results = run_payroll(drivers)
    return jsonify({"results": results})

@app.post("/api/payroll/export")
def export_payroll_csv():
    payload = request.get_json(force=True) or {}
    drivers = payload.get("drivers", [])
    results = run_payroll(drivers)
    csv_data = settlements_to_csv(results)

    return (
        csv_data,
        200,
        {
            "Content-Type": "text/csv",
            "Content-Disposition": "attachment; filename=freightpay_settlements.csv"
        }
    )

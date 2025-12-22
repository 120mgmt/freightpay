from flask import Flask, request, jsonify
from payroll import run_payroll
from payroll.export_csv import settlements_to_csv

app = Flask(__name__)

@app.get("/")
def health():
    return jsonify({"status": "FreightPay running"})

@app.post("/api/payroll/run")
def api_run_payroll():
    payload = request.get_json(force=True) or {}
    contractors = payload.get("contractors", [])
    results = run_payroll(contractors)
    return jsonify({"results": results})

@app.post("/api/payroll/export/csv")
def api_export_csv():
    payload = request.get_json(force=True) or {}
    contractors = payload.get("contractors", [])
    results = run_payroll(contractors)
    csv_data = settlements_to_csv(results)
    return (csv_data, 200, {
        "Content-Type": "text/csv",
        "Content-Disposition": "attachment; filename=payroll_settlements.csv"
    })
@app.post("/api/payroll/run/miles")
def api_run_miles_payroll():
    payload = request.get_json(force=True) or {}
    drivers = payload.get("drivers", [])
    results = run_payroll(drivers)
    return jsonify({"results": results})

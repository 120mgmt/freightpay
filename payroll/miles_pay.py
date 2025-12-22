@app.post("/api/payroll/run/miles")
def api_run_miles_payroll():
    payload = request.get_json(force=True) or {}
    drivers = payload.get("drivers", [])
    results = run_payroll(drivers)
    return jsonify({"results": results})

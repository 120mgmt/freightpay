from flask import Flask, request, jsonify

app = Flask(__name__)

# =========================
# REGISTER BLUEPRINTS
# =========================
from bookkeeping.routes import bookkeeping_bp
app.register_blueprint(bookkeeping_bp)

# =========================
# HEALTH CHECK
# =========================
@app.get("/")
def health():
    return jsonify({
        "service": "payroll"
       "status": "FreightPay live"
    })

# =========================
# PAYROLL API
# =========================
from payroll.engine import run_payroll
from payroll.export_csv import settlements_to_csv

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
    return (
        csv_data,
        200,
        {
            "Content-Type": "text/csv",
            "Content-Disposition": "attachment; filename=payroll_settlements.csv"
        }
    )
 

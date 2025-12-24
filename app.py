import os
from flask import Flask, jsonify

# IMPORTANT:
# Your repo has a /payroll folder (not freightpay/routes), so import from payroll.*
from payroll.routes.payroll_routes import payroll_bp

# Optional bookkeeping imports (only keep if these files exist exactly as shown)
from bookkeeping.ledger import get_ledger
from bookkeeping.export_quickbooks import export_quickbooks_csv


app = Flask(__name__)

# Blueprints
app.register_blueprint(payroll_bp, url_prefix="/payroll")


# Health
@app.get("/")
def root():
    return jsonify({"app": "freightpay", "status": "running"}), 200


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


# Bookkeeping endpoints (simple, production-safe stubs)
@app.get("/bookkeeping/ledger")
def ledger():
    return jsonify(get_ledger()), 200


@app.get("/bookkeeping/export/quickbooks.csv")
def quickbooks_export():
    csv_text = export_quickbooks_csv()
    return (csv_text, 200, {"Content-Type": "text/csv"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)


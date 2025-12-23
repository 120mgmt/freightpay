from flask import Flask, jsonify, request, Response, render_template
import os
from freightpay.routes.payroll_routes import payroll_bp
# ─────────────────────────────────────────
# Imports
# ─────────────────────────────────────────

from bookkeeping.ledger import get_ledger
from bookkeeping.export_quickbooks import export_quickbooks_csv

# ─────────────────────────────────────────
# App init
# ─────────────────────────────────────────
app = Flask(__name__)
app.register_blueprint(payroll_bp, url_prefix="/payroll")
# ─────────────────────────────────────────
# Root / Health
# ─────────────────────────────────────────
@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "app": "freightpay",
        "status": "running"
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "service": "payroll",
        "status": "freightpay live"
    })

# ─────────────────────────────────────────
# Dashboard (UI)
# ─────────────────────────────────────────
@app.route("/dashboard", methods=["GET"])
def dashboard():
    return render_template("dashboard.html")

# ─────────────────────────────────────────
# Bookkeeping → QuickBooks CSV export
# ─────────────────────────────────────────
@app.route("/bookkeeping/quickbooks/export", methods=["GET"])
def export_quickbooks():
    ledger = get_ledger()
    csv_data = export_quickbooks_csv(ledger)

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=freightpay_quickbooks_export.csv"
        }
    )

# ─────────────────────────────────────────
# Run (Render / Gunicorn safe)
# ─────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

import os
from flask import Flask, jsonify

from payroll.routes.payroll_routes import payroll_bp

app = Flask(__name__)

# Register blueprint (blueprint already has /payroll prefix i nside it)
app.register_blueprint(payroll_bp)

@app.get("/")
def root():
    return jsonify({"app": "freightpay", "status": "running"}), 200

@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200

# Blueprints
app.register_blueprint(payroll_bp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

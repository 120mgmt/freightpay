# app.py
from __future__ import annotations

import os
from flask import Flask, jsonify

# Import blueprints AFTER app context is valid
from payroll.routes.payroll_routes import payroll_bp


def create_app() -> Flask:
    app = Flask(__name__)

    # ---- Core Config ----
    app.config["JSON_SORT_KEYS"] = False

    # ---- Health Check ----
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    # ---- Register Blueprints ----
    app.register_blueprint(payroll_bp)

    return app


# Gunicorn entrypoint
app = create_app()

# Local dev only (Render ignores this)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

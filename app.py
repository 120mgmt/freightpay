# app.py
from __future__ import annotations

import os
import sys
from flask import Flask, jsonify

# Ensure imports work in Render regardless of working directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")

# Put BASE_DIR first so top-level packages like /billing and /payroll resolve
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# If a /src folder exists, include it too (safe/no harm if unused)
if os.path.isdir(SRC_DIR) and SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# Blueprints
from payroll.routes.payroll_routes import payroll_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    app.register_blueprint(payroll_bp)
    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

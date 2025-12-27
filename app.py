# app.py
from __future__ import annotations

import os
from flask import Flask, jsonify

# Blueprints
from payroll.routes.payroll_routes import payroll_bp


def create_app() -> Flask:
    app = Flask(__name__)

    # Core config
    app.config["JSON_SORT_KEYS"] = False

    # Health check
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    # Register blueprints
    app.register_blueprint(payroll_bp)

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

# app.py
from __future__ import annotations

import os
import sys

from flask import Flask, jsonify

# ===== PATH FIX (PRODUCTION) =====
# Render runs from: /opt/render/project/src
# billing/, payroll/, etc. are inside the same /src directory.
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
# ================================

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

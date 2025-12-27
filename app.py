# app.py
from __future__ import annotations

import os
import sys
from flask import Flask, jsonify

# ===== PATH FIX (THIS IS THE FIX) =====
# app.py lives in /opt/render/project/src
# billing/, payroll/, etc live in /opt/render/project
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# =====================================


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

import os
from flask import Flask, jsonify

from payroll.routes.payroll_routes import payroll_bp


def create_app() -> Flask:
    app = Flask(__name__)

    # Health
    @app.get("/")
    def root():
        return jsonify({"app": "freightpay", "status": "running"}), 200

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"}), 200

    # Blueprints
    app.register_blueprint(payroll_bp)

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

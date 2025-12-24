import os
import sys
from flask import Flask, jsonify
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager

# Ensure /src is on the import path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from config import Config
from models import db
from auth.routes import auth_bp
from payroll.routes.payroll_routes import payroll_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    Migrate(app, db)
    JWTManager(app)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"}), 200

    app.register_blueprint(auth_bp)
    app.register_blueprint(payroll_bp)

    return app


app = create_app()

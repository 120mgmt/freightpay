from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from models import db, User

auth_bp = Blueprint("auth_api", __name__, url_prefix="/auth")

@auth_bp.post("/register")
def register():
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email_and_password_required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email_already_exists"}), 409

    u = User(email=email)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()

    token = create_access_token(identity=str(u.id))
    return jsonify({"status": "ok", "access_token": token}), 201

@auth_bp.post("/login")
def login():
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    u = User.query.filter_by(email=email).first()
    if not u or not u.check_password(password):
        return jsonify({"error": "invalid_credentials"}), 401

    token = create_access_token(identity=str(u.id))
    return jsonify({"status": "ok", "access_token": token}), 200

from flask import Blueprint, jsonify
from utils.auth import require_auth
from models import User

users_bp = Blueprint("users", __name__, url_prefix="/users")


@users_bp.get("/me")
@require_auth
def me(user: User):
    return jsonify(
        {
            "id": user.id,
            "email": user.email,
            "accepted_tos": bool(user.accepted_tos),
            "accepted_privacy": bool(user.accepted_privacy),
            "subscription_active": bool(getattr(user, "subscription_active", False)),
        }
    ), 200

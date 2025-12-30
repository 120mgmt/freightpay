from flask import jsonify
from utils.auth import get_current_user

EXEMPT_PATHS = (
    "/legal/terms",
    "/legal/privacy",
    "/legal/accept",
    "/auth/login",
    "/auth/register"
)

def enforce_legal_acceptance():
    user = get_current_user()
    if not user:
        return

    if not user.accepted_tos or not user.accepted_privacy:
        return jsonify({
            "error": "Legal acceptance required",
            "required": ["terms", "privacy"]
        }), 403

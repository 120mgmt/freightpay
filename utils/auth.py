from functools import wraps
from flask import request, jsonify

from models import User
from utils.database import get_db


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = request.headers.get("X-User-Id")
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401

        db = get_db()
        try:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if not user:
                return jsonify({"error": "Unauthorized"}), 401
            return fn(user=user, db=db, *args, **kwargs)
        finally:
            db.close()

    return wrapper

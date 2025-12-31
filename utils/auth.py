# utils/auth.py

from __future__ import annotations

import os
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Tuple, Callable, Any

import jwt
from flask import request, jsonify, g
from sqlalchemy.orm import Session

from models import User
from utils.database import get_db

JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret")
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_HOURS = int(os.getenv("JWT_EXPIRES_HOURS", "24"))


def _encode_token(user_id: str) -> str:
    payload = {
        "sub": user_id,  # UUID string
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRES_HOURS),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    # PyJWT may return str (v2+) or bytes (older); normalize
    return token.decode("utf-8") if isinstance(token, (bytes, bytearray)) else token


def _decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        if not sub:
            return None
        return str(sub)
    except Exception:
        return None


def get_current_user() -> Optional[User]:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header.replace("Bearer ", "").strip()
    user_id = _decode_token(token)
    if not user_id:
        return None

    db: Session = get_db()
    return db.query(User).filter(User.id == user_id).first()


def require_auth(fn: Callable[..., Any]):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user or not getattr(user, "is_active", True):
            return jsonify({"error": "AUTH_REQUIRED"}), 401

        g.current_user = user
        return fn(user=user, *args, **kwargs)

    return wrapper


def login_user(email: str, password: str) -> Tuple[Optional[str], Optional[User]]:
    db: Session = get_db()
    user = db.query(User).filter(User.email == email.lower().strip()).first()
    if not user:
        return None, None

    if not user.check_password(password):
        return None, None

    token = _encode_token(str(user.id))
    return token, user

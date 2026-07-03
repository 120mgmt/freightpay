# jwt_config.py — single JWT entrypoint (app.py calls init_jwt(app) after Flask() creation)

from __future__ import annotations

import os
from datetime import timedelta
from typing import Any, Dict

from flask import jsonify
from flask_jwt_extended import JWTManager


def init_jwt(app) -> JWTManager:
    """
    Call from app.py after app = Flask(__name__). Single auth JWT init for flat-root layout.

    Required ENV:
      - JWT_SECRET_KEY (set a long random value in Render)
    Optional ENV:
      - JWT_ACCESS_TOKEN_EXPIRES_SECONDS (default 43200 = 12 hours)
    """
    secret = (os.getenv("JWT_SECRET_KEY") or "").strip()
    if not secret or len(secret) < 32:
        raise RuntimeError("JWT_SECRET_KEY is required (min 32 chars)")

    try:
        expires_seconds = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_SECONDS", "43200"))
        if expires_seconds < 300:
            raise ValueError("too small")
        if expires_seconds > 86400:
            raise ValueError("too large — max 86400 seconds (24 hours)")
    except ValueError as e:
        raise RuntimeError(f"JWT_ACCESS_TOKEN_EXPIRES_SECONDS invalid: {e}")
    except Exception:
        raise RuntimeError("JWT_ACCESS_TOKEN_EXPIRES_SECONDS must be an integer between 300 and 86400")

    import logging as _log
    _log.getLogger("ledgerhaul").info(
        "JWT configured: expires_seconds=%d (%.1f hours)",
        expires_seconds,
        expires_seconds / 3600,
    )

    app.config["JWT_SECRET_KEY"] = secret
    # The app uses a dict identity ({user_id, company_id, role, email}).
    # PyJWT >= 2.10 rejects tokens whose "sub" claim is not a string, so we
    # store the identity under a custom claim instead of "sub".
    app.config["JWT_IDENTITY_CLAIM"] = "identity"
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_HEADER_NAME"] = "Authorization"
    app.config["JWT_HEADER_TYPE"] = "Bearer"
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(seconds=expires_seconds)

    jwt = JWTManager(app)

    # -------------------------
    # Hardened error responses
    # -------------------------
    @jwt.unauthorized_loader
    def _unauthorized(msg: str):
        return jsonify({"error": "missing_token", "detail": msg}), 401

    @jwt.invalid_token_loader
    def _invalid(msg: str):
        return jsonify({"error": "invalid_token", "detail": msg}), 401

    @jwt.expired_token_loader
    def _expired(jwt_header: Dict[str, Any], jwt_payload: Dict[str, Any]):
        return jsonify({"error": "token_expired"}), 401

    @jwt.revoked_token_loader
    def _revoked(jwt_header: Dict[str, Any], jwt_payload: Dict[str, Any]):
        return jsonify({"error": "token_revoked"}), 401

    return jwt

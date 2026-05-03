# File: utils/auth.py
# Purpose: Auth helpers for LedgerHaul (Flask-JWT-Extended compatible) + legal_guard support
# Status: Production-ready
# Date: 2026-02-08

from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable, Dict, Optional, TypeVar, cast

from sqlalchemy.exc import SQLAlchemyError

from db import db
from models.user import User

T = TypeVar("T")


def get_current_user() -> Optional[User]:
    """
    Resolve the current authenticated user for request-scoped guards (ex: utils/legal_guard.py).

    - Safe inside @app.before_request
    - Returns None if no/invalid JWT
    - Uses Flask-JWT-Extended identity payload format:
        {"user_id": ..., "company_id": ..., "role": ..., "email": ...}
    """
    try:
        # Import inside function to avoid import-time failures if JWT isn't initialized yet
        from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request  # type: ignore

        verify_jwt_in_request(optional=True)
        identity: Any = get_jwt_identity()
        if not identity or not isinstance(identity, dict):
            return None

        user_id = identity.get("user_id")
        if not user_id:
            return None

        return db.session.get(User, int(user_id))

    except SQLAlchemyError:
        return None
    except Exception:
        return None


def require_auth(fn: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator: require a valid JWT and an active user record.

    Usage:
      @require_auth
      def handler(...):
          ...

    The user is made available as request.current_user for downstream logic.
    """
    from functools import wraps
    from flask import request

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        from flask_jwt_extended import verify_jwt_in_request  # type: ignore

        verify_jwt_in_request(optional=False)

        u = get_current_user()
        if not u or not getattr(u, "is_active", False):
            # Avoid leaking which part failed
            from flask import abort
            abort(401)

        # Attach to request for convenience
        setattr(request, "current_user", u)

        return fn(*args, **kwargs)

    return cast(Callable[..., T], wrapper)


def login_user(
    *,
    user: User,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create an access token for a user using the project’s identity format.

    Returns: JWT access token string.
    """
    from flask_jwt_extended import create_access_token  # type: ignore

    identity = {
        "user_id": int(user.id),
        "company_id": int(user.company_id),
        "role": getattr(user, "role", "viewer"),
        "email": getattr(user, "email", ""),
    }

    claims = dict(additional_claims or {})
    # Keep minimal, stable claims; identity already contains tenant + role
    return create_access_token(identity=identity, expires_delta=expires_delta, additional_claims=claims)

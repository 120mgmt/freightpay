# freightpay/legal/middleware.py
# Purpose: Enforce legal acceptance for protected routes
# Status: Full deployment – production v5
# Date: 2026-01-01

from __future__ import annotations

from functools import wraps
from typing import Callable, Any, TypeVar, cast

from flask import jsonify
from sqlalchemy.orm import Session

from utils.database import get_db
from models import User
from legal.service import has_current_legal_acceptance

F = TypeVar("F", bound=Callable[..., Any])


def require_legal_acceptance(fn: F) -> F:
    """
    Use AFTER @require_auth.

    Example:
      @bp.get("/dashboard")
      @require_auth
      @require_legal_acceptance
      def dashboard(user: User): ...
    """

    @wraps(fn)
    def wrapper(user: User, *args: Any, **kwargs: Any):
        db: Session = get_db()
        if not has_current_legal_acceptance(db, user):
            return (
                jsonify(
                    {
                        "error": "LEGAL_ACCEPTANCE_REQUIRED",
                        "action": "POST /legal/acceptance",
                    }
                ),
                403,
            )
        return fn(user, *args, **kwargs)

    return cast(F, wrapper)

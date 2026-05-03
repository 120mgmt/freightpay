# File: middleware/rbac.py
# Purpose: Enterprise Role-Based Access Control (RBAC) enforcement layer
# Status: Enterprise-hardened (company-scoped, role-locked, financial-route safe)
# Date: 2026-02-26

from __future__ import annotations

from functools import wraps
from typing import List

from flask import request, jsonify
from utils.auth import get_current_user


def _get_user():
    try:
        user = get_current_user()
        if not isinstance(user, dict):
            return None
        return user
    except Exception:
        return None


def _require_company_scope(user: dict, company_id: int) -> bool:
    # Assumes user object contains allowed company_ids list
    allowed = user.get("company_ids") or []
    return int(company_id) in [int(x) for x in allowed]


def require_roles(allowed_roles: List[str]):
    """
    Usage:
        @require_roles(["admin", "finance"])
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):

            user = _get_user()
            if not user:
                return jsonify({"error": "unauthorized"}), 401

            role = (user.get("role") or "").lower()
            if role not in [r.lower() for r in allowed_roles]:
                return jsonify({"error": "forbidden"}), 403

            company_id = (
                request.headers.get("X-Company-Id")
                or request.args.get("company_id")
                or (request.get_json(silent=True) or {}).get("company_id")
            )

            if company_id is None:
                return jsonify({"error": "missing_company_scope"}), 400

            try:
                company_id = int(str(company_id).strip())
            except Exception:
                return jsonify({"error": "invalid_company_scope"}), 400

            if not _require_company_scope(user, company_id):
                return jsonify({"error": "company_scope_violation"}), 403

            return fn(*args, **kwargs)

        return wrapper

    return decorator

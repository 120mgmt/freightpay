# File: compliance/audit_helpers.py
# Purpose: JWT-aware helpers to write compliance audit logs with request context
# Status: Production-ready (no Flask-Login)
# Date: 2026-01-26

from __future__ import annotations

from typing import Any, Optional, Tuple

from flask import request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

from compliance.audit import audit_log_event


def _client_ip() -> Optional[str]:
    # Respect proxies/CDN if configured; fall back to remote_addr
    xff = (request.headers.get("X-Forwarded-For") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return (request.headers.get("X-Real-Ip") or "").strip() or request.remote_addr


def _jwt_actor() -> Tuple[Optional[int], str, Optional[str]]:
    """
    Returns (user_id, actor_type, actor_role).
    actor_type: user|system|admin
    """
    try:
        verify_jwt_in_request(optional=True)
        identity: Any = get_jwt_identity()
        if not identity:
            return None, "system", None

        if isinstance(identity, dict):
            user_id = identity.get("user_id")
            role = identity.get("role")
        else:
            user_id = identity
            role = None

        actor_type = "admin" if role in {"admin", "owner", "superadmin"} else "user"
        return int(user_id) if user_id is not None else None, actor_type, role
    except Exception:
        return None, "system", None


def audit_compliance_event(
    *,
    event_type: str,
    doc_key: str | None = None,
    version: str | None = None,
) -> None:
    """
    Writes an audit record using JWT identity + request context.
    Never raises.
    """
    user_id, actor_type, actor_role = _jwt_actor()

    audit_log_event(
        event_type=event_type,
        user_id=user_id,
        actor_type=actor_type,
        actor_role=actor_role,
        doc_key=doc_key,
        version=version,
        path=(request.path or None),
        method=(request.method or None),
        ip=_client_ip(),
        user_agent=(request.headers.get("User-Agent") or None),
    )

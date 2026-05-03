# utils/admin_audit.py
# Purpose: Admin audit logging for sensitive financial controls (CPM)
# Status: Production-ready
# Date: 2026-01-28

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from flask import request
from flask_jwt_extended import get_jwt_identity

logger = logging.getLogger("ledgerhaul.audit")


def log_admin_action(
    *,
    action: str,
    resource: str,
    before: Dict[str, Any] | None = None,
    after: Dict[str, Any] | None = None,
) -> None:
    """
    Records an immutable audit log for admin actions.
    Intended for pricing, payroll controls, compliance settings.

    This does NOT block execution.
    This does NOT mutate data.
    """

    ident = get_jwt_identity() or {}

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "action": action,
        "resource": resource,
        "actor_id": ident.get("user_id"),
        "actor_role": ident.get("role"),
        "company_id": ident.get("company_id"),
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
        "user_agent": request.headers.get("User-Agent"),
        "before": before,
        "after": after,
    }

    # Structured log — can be shipped to SIEM later
    logger.info("ADMIN_AUDIT %s", entry)

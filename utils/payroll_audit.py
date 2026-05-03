# File: utils/payroll_audit.py
# Purpose: Centralized payroll audit logging helper
# Status: Production-ready / hardened
# Date: 2026-02-18

from __future__ import annotations

from flask import request
from db import db
from models.payroll_audit_log import PayrollAuditLog


def log_payroll_event(
    *,
    company_id: int,
    user_id: int | None,
    payroll_id: int | None,
    action: str,
    entity_type: str,
    metadata: dict | None = None,
) -> None:
    """
    Append-only payroll audit logger.
    """

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent")

    log = PayrollAuditLog(
        company_id=company_id,
        user_id=user_id,
        payroll_id=payroll_id,
        action=action,
        entity_type=entity_type,
        metadata=metadata or {},
        ip_address=ip,
        user_agent=ua,
    )

    db.session.add(log)
    db.session.commit()

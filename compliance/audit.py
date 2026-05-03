# File: compliance/audit.py
# Purpose: Compliance audit log (legal acceptance, enforcement blocks, version activation)
# Status: Production-ready (JWT-compatible, no Flask-Login)
# Date: 2026-01-26

from __future__ import annotations

from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.sql import func

from db import db


class ComplianceAuditLog(db.Model):
    __tablename__ = "compliance_audit_logs"

    id = Column(Integer, primary_key=True)

    # Actor context (nullable for system/background events)
    user_id = Column(Integer, nullable=True, index=True)
    actor_type = Column(String(32), nullable=False, default="user")  # user|system|admin
    actor_role = Column(String(64), nullable=True)

    # Event context
    event_type = Column(String(64), nullable=False, index=True)  # legal_accepted|legal_blocked|legal_seeded|doc_activated
    doc_key = Column(String(64), nullable=True)
    version = Column(String(64), nullable=True)

    # Request context (optional; set by caller)
    path = Column(String(512), nullable=True)
    method = Column(String(16), nullable=True)
    ip = Column(String(64), nullable=True)
    user_agent = Column(String(256), nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())


Index("ix_compliance_audit_event_time", ComplianceAuditLog.event_type, ComplianceAuditLog.created_at)


def audit_log_event(
    *,
    event_type: str,
    user_id: int | None = None,
    actor_type: str = "user",
    actor_role: str | None = None,
    doc_key: str | None = None,
    version: str | None = None,
    path: str | None = None,
    method: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """
    Lightweight writer. Caller supplies context (JWT identity + Flask request values).
    Never raises — audit logging must not break primary flows.
    """
    try:
        rec = ComplianceAuditLog(
            user_id=user_id,
            actor_type=actor_type,
            actor_role=actor_role,
            event_type=event_type,
            doc_key=doc_key,
            version=version,
            path=path,
            method=method,
            ip=ip,
            user_agent=user_agent,
        )
        db.session.add(rec)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass

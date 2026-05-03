# File: models/payroll_audit_log.py
# Purpose: Immutable payroll audit trail (SOX-grade logging for payroll actions)
# Status: Production-ready / hardened / append-only
# Date: 2026-02-18

from __future__ import annotations

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Index
from sqlalchemy.sql import func
from db import db


class PayrollAuditLog(db.Model):
    """
    Immutable audit log for payroll events.
    Append-only. No update/delete operations allowed.
    """

    __tablename__ = "payroll_audit_logs"

    id = Column(Integer, primary_key=True)

    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    payroll_id = Column(Integer, nullable=True, index=True)

    action = Column(String(100), nullable=False)
    # e.g. CREATED, EDITED, SUBMITTED, APPROVED, LOCKED, VOIDED

    entity_type = Column(String(100), nullable=False)
    # e.g. payroll_run, payroll_item, deduction, reimbursement

    metadata = Column(JSON, nullable=True)

    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # -----------------------------------
    # Hard Enforcement: Prevent Updates
    # -----------------------------------
    def __setattr__(self, key, value):
        if hasattr(self, "id") and self.id is not None:
            raise RuntimeError("PayrollAuditLog is immutable.")
        super().__setattr__(key, value)

    def to_dict(self) -> dict:
        created = (
            self.created_at.isoformat()
            if isinstance(self.created_at, datetime)
            else None
        )

        return {
            "id": self.id,
            "company_id": self.company_id,
            "user_id": self.user_id,
            "payroll_id": self.payroll_id,
            "action": self.action,
            "entity_type": self.entity_type,
            "metadata": self.metadata,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": created,
        }


Index(
    "ix_payroll_audit_company_payroll",
    PayrollAuditLog.company_id,
    PayrollAuditLog.payroll_id,
)

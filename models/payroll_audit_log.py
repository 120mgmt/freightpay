# File: models/payroll_audit_log.py
# Purpose: Append-only payroll audit log model
# Status: Enterprise hardened
# Date: 2026-03-05

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import JSONB

from db import db


class PayrollAuditLog(db.Model):
    __tablename__ = "payroll_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    user_id = db.Column(db.Integer, nullable=True, index=True)
    payroll_id = db.Column(db.Integer, nullable=True, index=True)

    action = db.Column(db.String(100), nullable=False, index=True)
    entity_type = db.Column(db.String(100), nullable=False, index=True)

    metadata = db.Column(
        JSONB().with_variant(db.JSON, "sqlite"),
        nullable=False,
        default=dict,
    )

    ip_address = db.Column(db.String(128), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "user_id": self.user_id,
            "payroll_id": self.payroll_id,
            "action": self.action,
            "entity_type": self.entity_type,
            "metadata": self.metadata or {},
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

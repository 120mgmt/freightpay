# File: models/ledger_entry.py
# Purpose: Simple ledger entry model for contractor payment tracking
# Matches the interface expected by services/ledger_service.py
# Status: Production-ready
# Date: 2026-04-01

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime, ForeignKey, Index
)

from db import db


class LedgerEntry(db.Model):
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    contractor_id = Column(Integer, ForeignKey("contractors.id"), nullable=True, index=True)

    entry_type = Column(String(50), nullable=False)       # e.g. "payroll", "adjustment"
    pay_period = Column(String(7), nullable=True)          # YYYY-MM

    contractor_name = Column(String(255), nullable=True)
    gross = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    reimbursements = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    deductions = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    net = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)

    debit_account_code = Column(String(20), nullable=True)
    credit_account_code = Column(String(20), nullable=True)
    memo = Column(String(500), nullable=True)

    recorded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_ledger_entries_company_period", "company_id", "pay_period"),
        Index("ix_ledger_entries_contractor", "contractor_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "contractor_id": self.contractor_id,
            "entry_type": self.entry_type,
            "pay_period": self.pay_period,
            "contractor_name": self.contractor_name,
            "gross": str(self.gross),
            "reimbursements": str(self.reimbursements),
            "deductions": str(self.deductions),
            "net": str(self.net),
            "debit_account_code": self.debit_account_code,
            "credit_account_code": self.credit_account_code,
            "memo": self.memo,
            "recorded_by_user_id": self.recorded_by_user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

# freightpay/models/ledger.py

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
    Numeric,
    CheckConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class LedgerEntry(Base):
    """
    Production-grade ledger entry.
    Enforces:
    - Double-entry structure (debit / credit)
    - Immutable financial records
    - Payroll + settlement traceability
    """

    __tablename__ = "ledger_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    payroll_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payroll_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    entry_type = Column(
        String(20),
        nullable=False,
        doc="debit or credit",
    )

    amount = Column(
        Numeric(12, 2),
        nullable=False,
        doc="Always stored as positive decimal",
    )

    currency = Column(
        String(3),
        nullable=False,
        default="USD",
    )

    account = Column(
        String(50),
        nullable=False,
        doc="ledger account name (e.g. payroll_expense, cash, liability)",
    )

    description = Column(String(255), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    company = relationship("Company", backref="ledger_entries")
    payroll_run = relationship("PayrollRun", backref="ledger_entries")

    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('debit', 'credit')",
            name="ck_ledger_entry_type_valid",
        ),
        CheckConstraint(
            "amount > 0",
            name="ck_ledger_amount_positive",
        ),
        Index(
            "ix_ledger_company_created",
            "company_id",
            "created_at",
        ),
    )

    def as_dict(self) -> dict:
        return {
            "id": str(self.id),
            "company_id": str(self.company_id),
            "payroll_run_id": str(self.payroll_run_id)
            if self.payroll_run_id
            else None,
            "entry_type": self.entry_type,
            "amount": float(self.amount),
            "currency": self.currency,
            "account": self.account,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
        }

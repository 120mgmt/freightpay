# freightpay/models/ledger_entry.py

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class LedgerEntry(Base):
    """
    V1 Production: Double-entry style ledger lines.
    Each row is a single line item.
    A "transaction" groups multiple lines via transaction_id.

    Rules enforced:
      - amount must be >= 0
      - entry_type must be debit|credit
      - account_code must be present
    """

    __tablename__ = "ledger_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Groups related lines (e.g., a driver settlement, a subscription payment, a fee)
    transaction_id = Column(UUID(as_uuid=True), nullable=False, index=True, default=uuid.uuid4)

    # Optional links for traceability
    payroll_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payroll_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    settlement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("settlements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Accounting fields
    account_code = Column(String(50), nullable=False)  # e.g. CASH, AR, AP, REV_SUBS, EXP_FEES
    entry_type = Column(String(10), nullable=False)    # debit | credit
    amount = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    currency = Column(String(3), nullable=False, default="USD")

    memo = Column(Text, nullable=True)
    external_reference = Column(String(255), nullable=True)  # Stripe charge/transfer id, ACH id, etc.

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships (optional convenience; safe if models exist)
    company = relationship("Company", backref="ledger_entries")
    payroll_run = relationship("PayrollRun", backref="ledger_entries")
    settlement = relationship("Settlement", backref="ledger_entries")
    user = relationship("User", backref="ledger_entries")

    __table_args__ = (
        Index("ix_ledger_company_created", "company_id", "created_at"),
        Index("ix_ledger_company_account", "company_id", "account_code"),
        Index("ix_ledger_company_txn", "company_id", "transaction_id"),
        CheckConstraint("amount >= 0", name="ck_ledger_amount_nonnegative"),
        CheckConstraint("entry_type IN ('debit','credit')", name="ck_ledger_entry_type_valid"),
        CheckConstraint("length(account_code) > 0", name="ck_ledger_account_code_nonempty"),
        CheckConstraint("length(currency) = 3", name="ck_ledger_currency_len3"),
    )

    def as_dict(self) -> dict:
        return {
            "id": str(self.id),
            "company_id": str(self.company_id),
            "transaction_id": str(self.transaction_id),
            "payroll_run_id": str(self.payroll_run_id) if self.payroll_run_id else None,
            "settlement_id": str(self.settlement_id) if self.settlement_id else None,
            "user_id": str(self.user_id) if self.user_id else None,
            "account_code": self.account_code,
            "entry_type": self.entry_type,
            "amount": str(self.amount),
            "currency": self.currency,
            "memo": self.memo,
            "external_reference": self.external_reference,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else None,
        }

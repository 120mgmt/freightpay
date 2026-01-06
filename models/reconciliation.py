# models/reconciliation.py
# BANK STATEMENTS + RECONCILIATION STATUS — ROOT IMPORTS (Render-safe)

from __future__ import annotations

import uuid
from decimal import Decimal
from datetime import date

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    String,
    Boolean,
    ForeignKey,
    Numeric,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from models.base import Base


class BankStatement(Base):
    """
    Imported bank statement header (per account + period).
    """

    __tablename__ = "bank_statements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    account_code = Column(String(50), nullable=False)  # CASH / BANK account
    period_code = Column(String(7), nullable=False)    # YYYY-MM

    statement_date = Column(Date, nullable=False)
    starting_balance = Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    ending_balance = Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    lines = relationship(
        "BankStatementLine",
        back_populates="statement",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "account_code",
            "period_code",
            name="uq_bank_statement_company_account_period",
        ),
        Index("ix_bank_stmt_company_period", "company_id", "period_code"),
    )


class BankStatementLine(Base):
    """
    Individual transaction line from a bank statement.
    """

    __tablename__ = "bank_statement_lines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    statement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bank_statements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    txn_date = Column(Date, nullable=False)
    description = Column(String(255), nullable=True)
    amount = Column(Numeric(14, 2), nullable=False)

    matched = Column(Boolean, nullable=False, default=False)
    matched_journal_id = Column(
        UUID(as_uuid=True),
        ForeignKey("journals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    statement = relationship("BankStatement", back_populates="lines")

    __table_args__ = (
        Index("ix_bank_stmt_line_statement", "statement_id"),
        Index("ix_bank_stmt_line_matched", "matched"),
    )


class ReconciliationStatus(Base):
    """
    Final reconciliation record (account + period).
    """

    __tablename__ = "reconciliation_status"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    company_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    account_code = Column(String(50), nullable=False)
    period_code = Column(String(7), nullable=False)

    ledger_balance = Column(Numeric(14, 2), nullable=False)
    statement_balance = Column(Numeric(14, 2), nullable=False)

    is_reconciled = Column(Boolean, nullable=False, default=False)
    reconciled_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "account_code",
            "period_code",
            name="uq_reconciliation_company_account_period",
        ),
        Index("ix_reconciliation_company_period", "company_id", "period_code"),
    )

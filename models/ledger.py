# freightpay/models/ledger.py
# SYSTEM OF RECORD — PRODUCTION GRADE GENERAL LEDGER

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    DateTime,
    String,
    Numeric,
    CheckConstraint,
    ForeignKey,
    Index,
    Enum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class Journal(Base):
    """
    Journal header.
    One journal MUST have multiple ledger lines.
    """
    __tablename__ = "journals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_type = Column(
        Enum(
            "payroll",
            "tax",
            "payment",
            "adjustment",
            "reversal",
            "manual",
            name="journal_source_type",
        ),
        nullable=False,
    )

    source_id = Column(UUID(as_uuid=True), nullable=False)

    accounting_period = Column(
        String(7),  # YYYY-MM
        nullable=False,
        index=True,
    )

    description = Column(String(255), nullable=False)

    posted_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    posted_by = Column(UUID(as_uuid=True), nullable=False)

    entries = relationship(
        "LedgerEntry",
        back_populates="journal",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class LedgerEntry(Base):
    """
    Immutable double-entry ledger line.
    """

    __tablename__ = "ledger_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    journal_id = Column(
        UUID(as_uuid=True),
        ForeignKey("journals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    account_code = Column(
        String(50),
        nullable=False,
        doc="Chart of Accounts code",
    )

    debit = Column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    credit = Column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    currency = Column(String(3), nullable=False, default="USD")

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    journal = relationship("Journal", back_populates="entries")

    __table_args__ = (
        CheckConstraint(
            "(debit = 0 AND credit > 0) OR (credit = 0 AND debit > 0)",
            name="ck_ledger_debit_credit_exclusive",
        ),
        Index(
            "ix_ledger_company_period",
            "company_id",
            "account_code",
        ),
    )

# freightpay/models/journal_entry.py
# Production-grade journal line model (separate from ledger system-of-record)
# Date: 2026-02-14

import uuid
from decimal import Decimal

from sqlalchemy import (
    Column,
    DateTime,
    String,
    Numeric,
    CheckConstraint,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class JournalEntry(Base):
    """
    JournalEntry represents transactional journal lines BEFORE
    permanent posting into the immutable LedgerEntry table.

    This allows:
    - Draft journals
    - Edit before posting
    - Migration imports
    - Validation before locking
    """

    __tablename__ = "journal_entries"

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

    account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chart_of_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    account_code = Column(
        String(50),
        nullable=False,
        doc="Snapshot of account code at time of entry",
    )

    description = Column(String(255), nullable=True)

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

    journal = relationship("Journal", backref="journal_lines")

    __table_args__ = (
        CheckConstraint(
            "(debit = 0 AND credit > 0) OR (credit = 0 AND debit > 0)",
            name="ck_journal_entry_debit_credit_exclusive",
        ),
        CheckConstraint(
            "debit >= 0 AND credit >= 0",
            name="ck_journal_entry_non_negative",
        ),
        Index(
            "ix_journal_entry_company_account",
            "company_id",
            "account_id",
        ),
        Index(
            "ix_journal_entry_company_journal",
            "company_id",
            "journal_id",
        ),
    )

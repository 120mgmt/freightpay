# freightpay/models/journal.py
# Journal header for double-entry accounting (system of record)

import uuid
from sqlalchemy import (
    Column,
    DateTime,
    String,
    ForeignKey,
    Index,
    Enum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class Journal(Base):
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

    source_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        doc="ID of originating object (payroll_run, settlement, etc.)",
    )

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


Index("ix_journal_company_period", Journal.company_id, Journal.accounting_period)

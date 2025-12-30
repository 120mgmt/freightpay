# freightpay/models/ledger.py

import uuid
from sqlalchemy import (
    Column,
    String,
    Float,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from .base import Base


class LedgerEntry(Base):
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

    description = Column(String(255), nullable=False)

    amount = Column(
        Float,
        nullable=False,  # positive = credit, negative = debit
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    company = relationship("Company", backref="ledger_entries")
    payroll_run = relationship("PayrollRun", backref="ledger_entries")


Index(
    "ix_ledger_company_created",
    LedgerEntry.company_id,
    LedgerEntry.created_at,
)

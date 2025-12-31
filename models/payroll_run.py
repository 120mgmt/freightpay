# freightpay/models/payroll_run.py

import uuid
from datetime import date
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    String,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class PayrollRun(Base):
    """
    Production payroll run.
    Guarantees:
    - Immutable payroll periods
    - One payroll per company per period
    - Traceable to ledger + settlements
    """

    __tablename__ = "payroll_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    status = Column(
        String(20),
        nullable=False,
        default="draft",
        doc="draft | approved | processed | paid | voided",
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    finalized_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Set once payroll is locked",
    )

    # Relationships
    company = relationship("Company", backref="payroll_runs")
    ledger_entries = relationship(
        "LedgerEntry",
        backref="payroll_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint(
            "period_end >= period_start",
            name="ck_payroll_period_valid",
        ),
        CheckConstraint(
            "status IN ('draft','approved','processed','paid','voided')",
            name="ck_payroll_status_valid",
        ),
        Index(
            "ix_payroll_company_period_unique",
            "company_id",
            "period_start",
            "period_end",
            unique=True,
        ),
    )

    def lock(self):
        """Irreversibly finalize payroll."""
        if self.finalized_at is not None:
            return
        self.finalized_at = func.now()
        self.status = "processed"

    def as_dict(self) -> dict:
        return {
            "id": str(self.id),
            "company_id": str(self.company_id),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "finalized_at": self.finalized_at.isoformat()
            if self.finalized_at
            else None,
        }

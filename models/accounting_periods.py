# freightpay/models/accounting_periods.py
# ACCOUNTING PERIODS + LOCKING (COMPLIANCE ENFORCEMENT)

import uuid
from datetime import date

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    String,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from .base import Base


class AccountingPeriod(Base):
    """
    Enforced accounting periods.
    Controls posting, locking, and audit compliance.
    """

    __tablename__ = "accounting_periods"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    period_code = Column(
        String(7),  # YYYY-MM
        nullable=False,
    )

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    is_closed = Column(Boolean, nullable=False, default=False)
    is_hard_locked = Column(Boolean, nullable=False, default=False)

    closed_at = Column(DateTime(timezone=True), nullable=True)
    closed_by = Column(UUID(as_uuid=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    company = relationship("Company", backref="accounting_periods")

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "period_code",
            name="uq_accounting_period_company_code",
        ),
        CheckConstraint(
            "start_date <= end_date",
            name="ck_accounting_period_dates_valid",
        ),
        Index(
            "ix_accounting_period_company_closed",
            "company_id",
            "is_closed",
        ),
    )

    def as_dict(self) -> dict:
        return {
            "id": str(self.id),
            "company_id": str(self.company_id),
            "period_code": self.period_code,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "is_closed": self.is_closed,
            "is_hard_locked": self.is_hard_locked,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "closed_by": str(self.closed_by) if self.closed_by else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

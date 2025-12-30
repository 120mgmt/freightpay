# freightpay/models/payroll_run.py

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class PayrollRun(Base):
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

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    company = relationship("Company", backref="payroll_runs")


Index(
    "ix_payroll_runs_company_period",
    PayrollRun.company_id,
    PayrollRun.period_start,
    PayrollRun.period_end,
    unique=True,
)

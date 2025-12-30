# freightpay/models/settlement.py

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class Settlement(Base):
    __tablename__ = "settlements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    payroll_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payroll_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    driver_id = Column(
        UUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    gross = Column(Numeric(12, 2), nullable=False, default=0)
    deductions = Column(Numeric(12, 2), nullable=False, default=0)
    net = Column(Numeric(12, 2), nullable=False, default=0)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    payroll_run = relationship("PayrollRun", backref="settlements")
    driver = relationship("Driver", backref="settlements")


Index(
    "ix_settlements_run_driver",
    Settlement.payroll_run_id,
    Settlement.driver_id,
    unique=True,
)

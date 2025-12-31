# freightpay/models/settlement.py

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    CheckConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class Settlement(Base):
    """
    Driver-level finalized settlement for a payroll run.
    One row = one driver payout.
    Immutable once completed.
    """

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

    method = Column(
        String(20),
        nullable=False,
        default="ach",
        doc="ach | stripe | manual",
    )

    status = Column(
        String(20),
        nullable=False,
        default="pending",
        doc="pending | submitted | completed | failed | reversed",
    )

    gross = Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    deductions = Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    net = Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    external_reference = Column(
        String(255),
        nullable=True,
        doc="ACH batch ID / Stripe transfer ID",
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    payroll_run = relationship("PayrollRun", backref="settlements")
    driver = relationship("Driver", backref="settlements")

    __table_args__ = (
        # One settlement per driver per payroll run
        Index(
            "ix_settlements_run_driver",
            "payroll_run_id",
            "driver_id",
            unique=True,
        ),
        # Accounting integrity
        CheckConstraint(
            "gross >= 0",
            name="ck_settlement_gross_positive",
        ),
        CheckConstraint(
            "deductions >= 0",
            name="ck_settlement_deductions_positive",
        ),
        CheckConstraint(
            "net = gross - deductions",
            name="ck_settlement_net_valid",
        ),
        CheckConstraint(
            "status IN ('pending','submitted','completed','failed','reversed')",
            name="ck_settlement_status_valid",
        ),
        CheckConstraint(
            "method IN ('ach','stripe','manual')",
            name="ck_settlement_method_valid",
        ),
    )

    def mark_completed(self, reference: str | None = None):
        """Finalize payout — irreversible."""
        if self.completed_at is not None:
            return
        self.status = "completed"
        self.completed_at = func.now()
        if reference:
            self.external_reference = reference

    def as_dict(self) -> dict:
        return {
            "id": str(self.id),
            "payroll_run_id": str(self.payroll_run_id),
            "driver_id": str(self.driver_id),
            "method": self.method,
            "status": self.status,
            "gross": str(self.gross),
            "deductions": str(self.deductions),
            "net": str(self.net),
            "external_reference": self.external_reference,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
        }

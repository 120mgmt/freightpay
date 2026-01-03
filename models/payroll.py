from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Boolean,
    Integer,
    Numeric,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from freightpay.db import Base


# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

PAY_TYPES = ("per_mile", "flat_rate", "percentage", "hourly")
SETTLEMENT_STATUS = ("draft", "approved", "paid", "voided")


# ─────────────────────────────────────────────
# SETTLEMENT (CORE)
# ─────────────────────────────────────────────

class PayrollSettlement(Base):
    __tablename__ = "payroll_settlements"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    contractor_id = Column(String, nullable=False, index=True)

    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    pay_type = Column(Enum(*PAY_TYPES, name="pay_type"), nullable=False)
    rate = Column(Numeric(12, 4), nullable=False)
    units = Column(Numeric(12, 4), nullable=False, default=Decimal("0"))
    revenue = Column(Numeric(12, 2), nullable=True)

    status = Column(Enum(*SETTLEMENT_STATUS, name="settlement_status"), nullable=False, default="draft")

    # Calculated values (stored for reporting only; source of truth = audit snapshot)
    gross_amount = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    adjusted_gross_amount = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    net_amount = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "contractor_id",
            "period_start",
            "period_end",
            name="uq_contractor_period",
        ),
    )

    accessorials = relationship("PayrollAccessorial", back_populates="settlement", cascade="all, delete-orphan")
    deductions = relationship("PayrollDeduction", back_populates="settlement", cascade="all, delete-orphan")
    escrow_entries = relationship("PayrollEscrow", back_populates="settlement", cascade="all, delete-orphan")
    audits = relationship("PayrollAudit", back_populates="settlement", cascade="all, delete-orphan")


# ─────────────────────────────────────────────
# ACCESSORIALS
# ─────────────────────────────────────────────

class PayrollAccessorial(Base):
    __tablename__ = "payroll_accessorials"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    settlement_id = Column(String, ForeignKey("payroll_settlements.id"), nullable=False)

    type = Column(String, nullable=False)
    description = Column(String, nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    settlement = relationship("PayrollSettlement", back_populates="accessorials")


# ─────────────────────────────────────────────
# DEDUCTIONS
# ─────────────────────────────────────────────

class PayrollDeduction(Base):
    __tablename__ = "payroll_deductions"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    settlement_id = Column(String, ForeignKey("payroll_settlements.id"), nullable=False)

    category = Column(String, nullable=False)
    description = Column(String, nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)

    recoverable = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    settlement = relationship("PayrollSettlement", back_populates="deductions")


# ─────────────────────────────────────────────
# ESCROW
# ─────────────────────────────────────────────

class PayrollEscrow(Base):
    __tablename__ = "payroll_escrow"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    contractor_id = Column(String, nullable=False, index=True)
    settlement_id = Column(String, ForeignKey("payroll_settlements.id"), nullable=True)

    amount = Column(Numeric(12, 2), nullable=False)
    is_release = Column(Boolean, default=False, nullable=False)

    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    settlement = relationship("PayrollSettlement", back_populates="escrow_entries")


# ─────────────────────────────────────────────
# AUDIT SNAPSHOT (IMMUTABLE)
# ─────────────────────────────────────────────

class PayrollAudit(Base):
    __tablename__ = "payroll_audits"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    settlement_id = Column(String, ForeignKey("payroll_settlements.id"), nullable=False)

    action = Column(String, nullable=False)  # approved / voided / paid
    actor = Column(String, nullable=False)
    snapshot = Column(JSON, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    settlement = relationship("PayrollSettlement", back_populates="audits")

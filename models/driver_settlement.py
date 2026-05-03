# File: models/driver_settlement.py
# Purpose: FULL production-grade Driver Settlement Engine schema
# Status: Production-ready (constraints, indexing, precision-safe, audit hardened)
# Date: 2026-02-25

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    String,
    Numeric,
    DateTime,
    ForeignKey,
    Boolean,
    CheckConstraint,
    UniqueConstraint,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from db import db


def _uuid():
    return uuid.uuid4()


# ============================================================
# LOADS
# ============================================================

class Load(db.Model):
    __tablename__ = "loads"

    __table_args__ = (
        UniqueConstraint("company_id", "load_number", name="uq_company_load_number"),
        CheckConstraint("revenue_amount >= 0", name="ck_load_revenue_positive"),
        CheckConstraint("miles >= 0", name="ck_load_miles_positive"),
        Index("ix_load_company_status", "company_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )

    company_id: Mapped[int] = mapped_column(nullable=False, index=True)

    load_number: Mapped[str] = mapped_column(String(64), nullable=False)

    revenue_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=text("0")
    )

    miles: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )

    fuel_surcharge: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=text("0")
    )

    detention: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=text("0")
    )

    layover: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=text("0")
    )

    other_accessorials: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=text("0")
    )

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="open"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    assignments = relationship(
        "DriverAssignment",
        back_populates="load",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# ============================================================
# DRIVER ASSIGNMENTS
# ============================================================

class DriverAssignment(db.Model):
    __tablename__ = "driver_assignments"

    __table_args__ = (
        UniqueConstraint("load_id", "driver_id", name="uq_load_driver"),
        CheckConstraint("pay_rate >= 0", name="ck_pay_rate_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )

    load_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("loads.id", ondelete="CASCADE"),
        nullable=False,
    )

    driver_id: Mapped[int] = mapped_column(nullable=False, index=True)

    pay_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )

    pay_rate: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, server_default=text("0")
    )

    override_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    load = relationship("Load", back_populates="assignments")


# ============================================================
# DRIVER SETTLEMENT HEADER
# ============================================================

class DriverSettlement(db.Model):
    __tablename__ = "driver_settlements"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "driver_id",
            "period_label",
            name="uq_company_driver_period",
        ),
        Index("ix_settlement_company_driver", "company_id", "driver_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )

    company_id: Mapped[int] = mapped_column(nullable=False)

    driver_id: Mapped[int] = mapped_column(nullable=False)

    period_label: Mapped[str] = mapped_column(
        String(64), nullable=False
    )

    gross_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=text("0")
    )

    deductions: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=text("0")
    )

    net_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=text("0")
    )

    locked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    lines = relationship(
        "DriverSettlementLine",
        back_populates="settlement",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# ============================================================
# DRIVER SETTLEMENT LINE ITEMS
# ============================================================

class DriverSettlementLine(db.Model):
    __tablename__ = "driver_settlement_lines"

    __table_args__ = (
        Index("ix_settlement_line_settlement", "settlement_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )

    settlement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("driver_settlements.id", ondelete="CASCADE"),
        nullable=False,
    )

    load_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("loads.id", ondelete="SET NULL"),
        nullable=True,
    )

    description: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    settlement = relationship("DriverSettlement", back_populates="lines")


# ============================================================
# DRIVER ESCROW
# ============================================================

class DriverEscrow(db.Model):
    __tablename__ = "driver_escrow"

    __table_args__ = (
        UniqueConstraint(
            "company_id", "driver_id", name="uq_company_driver_escrow"
        ),
        CheckConstraint("balance >= 0", name="ck_escrow_balance_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )

    company_id: Mapped[int] = mapped_column(nullable=False)

    driver_id: Mapped[int] = mapped_column(nullable=False)

    balance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=text("0")
    )

    last_updated: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
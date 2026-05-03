# File: models/settlement_execution_log.py
# Purpose: Enterprise-grade settlement execution tracking, idempotency & audit trail
# Status: Full production hardened
# Date: 2026-02-25

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from db import db


def _uuid():
    return uuid.uuid4()


class SettlementExecutionLog(db.Model):
    __tablename__ = "settlement_execution_log"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "driver_id",
            "period_label",
            name="uq_execution_company_driver_period",
        ),
        Index("ix_execution_settlement_id", "settlement_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )

    company_id: Mapped[int] = mapped_column(nullable=False, index=True)

    driver_id: Mapped[int] = mapped_column(nullable=False, index=True)

    period_label: Mapped[str] = mapped_column(String(64), nullable=False)

    settlement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("driver_settlements.id", ondelete="CASCADE"),
        nullable=False,
    )

    executed_by_user_id: Mapped[int] = mapped_column(nullable=False)

    execution_hash: Mapped[str] = mapped_column(String(128), nullable=False)

    locked_after_execution: Mapped[bool] = mapped_column(nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
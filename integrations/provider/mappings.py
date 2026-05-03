# File: integrations/provider/mappings.py
# Purpose: Enterprise Tenant + Provider ID Mapping Layer (Provider-Agnostic)
# Status: Enterprise Hardened (strict uniqueness + scoped access ready)
# Date: 2026-02-26

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    DateTime,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import db


def _uuid():
    return uuid.uuid4()


# ============================================================
# COMPANY ↔ PROVIDER COMPANY MAPPING
# ============================================================

class ProviderCompanyMapping(db.Model):
    __tablename__ = "provider_company_mappings"

    __table_args__ = (
        UniqueConstraint("company_id", name="uq_provider_company_local"),
        UniqueConstraint("provider_company_id", name="uq_provider_company_external"),
        Index("ix_provider_company_provider", "provider_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_uuid,
    )

    company_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )

    provider_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    provider_company_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )


# ============================================================
# WORKER ↔ PROVIDER WORKER MAPPING
# ============================================================

class ProviderWorkerMapping(db.Model):
    __tablename__ = "provider_worker_mappings"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "worker_uuid",
            name="uq_worker_local",
        ),
        UniqueConstraint(
            "provider_worker_id",
            name="uq_worker_external",
        ),
        Index("ix_provider_worker_company", "company_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_uuid,
    )

    company_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )

    worker_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    provider_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    provider_worker_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )


# ============================================================
# PAYROLL RUN ↔ PROVIDER PAYROLL ID MAPPING
# ============================================================

class ProviderPayrollMapping(db.Model):
    __tablename__ = "provider_payroll_mappings"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "payroll_run_uuid",
            name="uq_payroll_local",
        ),
        UniqueConstraint(
            "provider_payroll_id",
            name="uq_payroll_external",
        ),
        Index("ix_provider_payroll_company", "company_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_uuid,
    )

    company_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )

    payroll_run_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    provider_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    provider_payroll_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

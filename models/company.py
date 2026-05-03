# File: models/company.py
# Purpose: Company/tenant model for LedgerHaul SaaS (sellable onboarding + auth)
# Status: FULL production-ready (Flask-SQLAlchemy, root imports, Render-safe)
# Date: 2026-02-08

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, String, Boolean, DateTime, Index, Integer
from sqlalchemy.sql import func

from db import db


class Company(db.Model):
    __tablename__ = "companies"

    # IMPORTANT:
    # Must match users.company_id type. Your users.company_id is INTEGER, so companies.id must be INTEGER
    # or Postgres will reject the FK ("incompatible types: integer and uuid").
    id = Column(Integer, primary_key=True, autoincrement=True)

    name = Column(String(160), nullable=False)
    slug = Column(String(160), nullable=False, unique=True, index=True)

    # Optional forward-compatible bridge to Stripe
    stripe_customer_id = Column(String(255), nullable=True, index=True)

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "id": int(self.id) if self.id is not None else None,
            "name": self.name,
            "slug": self.slug,
            "stripe_customer_id": self.stripe_customer_id,
            "is_active": bool(self.is_active),
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else None,
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else None,
        }


Index("ix_companies_active", Company.is_active)

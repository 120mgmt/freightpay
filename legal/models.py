# legal/models.py
# Purpose: Persist legal acceptance (Terms / Privacy / Refund) — matches migration 20260101_add_legal_acceptances
# Status: Full deployment – production v5
# Date: 2026-01-01

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from db import db


class LegalAcceptance(db.Model):
    """
    One row per user acceptance event: terms_version, privacy_version, refund_version.
    Schema matches migration 20260101_add_legal_acceptances.
    """
    __tablename__ = "legal_acceptances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    terms_version = Column(String(64), nullable=False)
    privacy_version = Column(String(64), nullable=False)
    refund_version = Column(String(64), nullable=False)

    accepted_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)
    # Hash of the legal document content at time of acceptance (SHA-256)
    # Provides proof of exactly what version the user accepted
    content_hash = Column(String(64), nullable=True)

    is_current = Column(Boolean, nullable=False, default=True)

    user = relationship("User", backref="legal_acceptances")


__all__ = ["LegalAcceptance"]
# freightpay/legal/models.py
# Purpose: Persist legal acceptance (Terms / Privacy / Refund)
# Status: Full deployment – production v5
# Date: 2026-01-01

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from utils.database import Base


class LegalAcceptance(Base):
    __tablename__ = "legal_acceptances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    terms_version = Column(String, nullable=False)
    privacy_version = Column(String, nullable=False)
    refund_version = Column(String, nullable=False)

    accepted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

    is_current = Column(Boolean, nullable=False, default=True)

    user = relationship("User", backref="legal_acceptances")

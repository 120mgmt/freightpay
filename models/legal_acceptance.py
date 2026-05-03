# freightpay/models/legal_acceptance.py

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from .base import Base


class LegalAcceptance(Base):
    __tablename__ = "legal_acceptances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # "tos" | "privacy" | "refund"
    document = Column(String(50), nullable=False)

    # optional version string (e.g., "1.0")
    version = Column(String(20), nullable=True)

    accepted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


Index("ix_legal_acceptances_user_document", LegalAcceptance.user_id, LegalAcceptance.document)

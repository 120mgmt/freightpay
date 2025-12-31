# freightpay/models/payment.py

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from .base import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    settlement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("settlements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    provider = Column(String(50), nullable=False)  # stripe | ach | gusto
    provider_payment_id = Column(String(255), nullable=True)

    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="USD")

    status = Column(
        String(50),
        nullable=False,
        default="pending",  # pending | succeeded | failed | reversed
    )

    paid_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    company = relationship("Company", backref="payments")
    settlement = relationship("Settlement", backref="payments")


Index("ix_payments_company_status", Payment.company_id, Payment.status)
Index("ix_payments_provider_id", Payment.provider, Payment.provider_payment_id)

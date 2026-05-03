# freightpay/models/subscription.py

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from .base import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    stripe_subscription_id = Column(String(255), nullable=False, unique=True)
    stripe_customer_id = Column(String(255), nullable=False)

    status = Column(
        String(50),
        nullable=False,
        default="active",  # active | trialing | past_due | canceled | unpaid
    )

    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    company = relationship("Company", backref="subscriptions")


Index("ix_subscriptions_company_status", Subscription.company_id, Subscription.status)

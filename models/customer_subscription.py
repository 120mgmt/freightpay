# freightpay/models/customer_subscription.py

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB

from .base import Base


class CustomerSubscription(Base):
    """
    Persists Stripe subscription state + entitlements for a Stripe customer.

    Used by:
      - billing/entitlement_store.py (upsert/read)
      - billing/webhooks.py (writes)
      - subscription gating (reads)
    """

    __tablename__ = "customer_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Stripe customer id (cus_...)
    customer_id = Column(String(255), nullable=False, unique=True, index=True)

    active = Column(Boolean, nullable=False, default=False)
    status = Column(String(50), nullable=True)  # active, trialing, canceled, past_due, etc.
    price_id = Column(String(255), nullable=True)  # price_...

    # JSON entitlements snapshot
    # - Postgres: JSONB
    # - Other DBs: falls back via Text (safe default)
    entitlements = Column(JSONB, nullable=True)

    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


Index("ix_customer_subscriptions_customer_id", CustomerSubscription.customer_id, unique=True)

# freightpay/models/pay_config.py

import uuid
from sqlalchemy import (
    Column,
    String,
    Float,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class PayConfig(Base):
    __tablename__ = "pay_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    driver_id = Column(
        UUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    pay_type = Column(
        String(32),  # e.g. per_mile, percentage, flat
        nullable=False,
    )

    rate = Column(
        Float,
        nullable=False,
    )

    driver = relationship("Driver", backref="pay_configs")


Index(
    "ix_pay_configs_driver_type",
    PayConfig.driver_id,
    PayConfig.pay_type,
    unique=True,
)

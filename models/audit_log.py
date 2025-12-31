# freightpay/models/audit_log.py

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from .base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    action = Column(String(100), nullable=False)  # e.g. PAYROLL_RUN_CREATED
    entity = Column(String(100), nullable=False)  # e.g. PayrollRun, Settlement
    entity_id = Column(String(100), nullable=True)

    metadata = Column(JSON, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    company = relationship("Company", backref="audit_logs")
    user = relationship("User", backref="audit_logs")


Index("ix_audit_logs_company_created", AuditLog.company_id, AuditLog.created_at)
Index("ix_audit_logs_action", AuditLog.action)

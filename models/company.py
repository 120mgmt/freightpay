# freightpay/models/company.py

import uuid
from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from .base import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name = Column(String(255), nullable=False)
    ein = Column(String(15), nullable=True, unique=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # FIX: remove backref="company" (conflicts with an existing Driver.company property)
    # Use back_populates to pair with Driver.company
    drivers = relationship(
        "Driver",
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Prefer back_populates here as well (pairs with PayrollRun.company)
    payroll_runs = relationship(
        "PayrollRun",
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


Index("ix_company_name", Company.name)
Index("ix_company_ein", Company.ein)

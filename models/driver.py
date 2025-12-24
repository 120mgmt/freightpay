from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from .base import Base

class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    name = Column(String, nullable=False)
    is_contractor = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

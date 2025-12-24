from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from .base import Base

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    ein = Column(String)
    created_at = Column(dateTime(timezone=True), server_default=func.now())

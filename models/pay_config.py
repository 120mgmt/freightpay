from sqlalchemy import Column, Integer, String, Float, ForeignKey
from .base import Base

class PayConfig(Base):
    __tablename__ = "pay_configs"

    id = Column(Integer, primary_key=True)
    driver_id = Column(Integer, ForeignKey("driver.id"), nullable=False)
    pay_type = Column(string, nullable=False)
    rate = Column(Float, nullable=False)

from sqlalchemy import Column, Integer, Float, ForeignKey
from .base import Base

class Settlement(Base):
    __tablename__ = "settlements"

    id = Column(Integer, primary_key=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    gross = Column(Float, default=0.0)
    deductions = Column(Float, default=0.0)
    net = Column(Float, default=0.0)

# models/periods.py
# FULL FILE — AccountingPeriod model (root-based). Fixes: ModuleNotFoundError: No module named 'models.periods'


from sqlalchemy import Column, Integer, String, DateTime, Boolean, UniqueConstraint
from sqlalchemy.sql import func

from db import db


class AccountingPeriod(db.Model):
    __tablename__ = "accounting_periods"

    id = Column(Integer, primary_key=True)

    company_id = Column(Integer, nullable=False, index=True)

    # YYYY-MM (lexicographically sortable)
    period = Column(String(7), nullable=False, index=True)

    is_closed = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now(), nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "period", name="uq_accounting_period_company_period"),
    )

    def __repr__(self) -> str:
        return f"<AccountingPeriod company_id={self.company_id} period={self.period} closed={self.is_closed}>"

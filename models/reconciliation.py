# models/reconciliation.py
# FULL FILE — reconciliation models (NO circular imports, root-based)

from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    Boolean,
    ForeignKey,
    Numeric,
    Enum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db import db


# =========================
# ENUMS
# =========================
class ReconciliationStatus(str):
    OPEN = "open"
    FINALIZED = "finalized"


# =========================
# BANK STATEMENT (HEADER)
# =========================
class BankStatement(db.Model):
    __tablename__ = "bank_statements"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, nullable=False)
    account_code = Column(String, nullable=False)
    period = Column(String, nullable=False)  # YYYY-MM

    statement_start = Column(Date, nullable=False)
    statement_end = Column(Date, nullable=False)
    ending_balance = Column(Numeric(12, 2), nullable=False)

    created_at = Column(DateTime, server_default=func.now())

    lines = relationship(
        "BankStatementLine",
        back_populates="statement",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# =========================
# BANK STATEMENT LINE
# =========================
class BankStatementLine(db.Model):
    __tablename__ = "bank_statement_lines"

    id = Column(Integer, primary_key=True)
    statement_id = Column(Integer, ForeignKey("bank_statements.id"), nullable=False)

    txn_date = Column(Date, nullable=False)
    description = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)

    matched = Column(Boolean, default=False)
    ledger_entry_id = Column(Integer, nullable=True)

    statement = relationship("BankStatement", back_populates="lines")


# =========================
# RECONCILIATION SUMMARY
# =========================
class Reconciliation(db.Model):
    __tablename__ = "reconciliations"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, nullable=False)
    account_code = Column(String, nullable=False)
    period = Column(String, nullable=False)

    ledger_balance = Column(Numeric(12, 2), nullable=False)
    statement_balance = Column(Numeric(12, 2), nullable=False)

    status = Column(
        Enum(
            ReconciliationStatus.OPEN,
            ReconciliationStatus.FINALIZED,
            name="reconciliation_status",
        ),
        nullable=False,
        default=ReconciliationStatus.OPEN,
    )

    is_reconciled = Column(Boolean, default=False)
    finalized_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())

# models/reconciliation.py
# FULL FILE — reconciliation models (NO circular imports, root-based)

from __future__ import annotations

from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, Numeric, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db import db


# =========================
# ENUMS (real Python Enum)
# =========================
class ReconciliationStatus(str, PyEnum):
    OPEN = "open"
    FINALIZED = "finalized"


# =========================
# BANK STATEMENT (HEADER)
# =========================
class BankStatement(db.Model):
    __tablename__ = "bank_statements"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, nullable=False, index=True)
    account_code = Column(String, nullable=False, index=True)
    period = Column(String, nullable=False, index=True)  # YYYY-MM

    statement_start = Column(Date, nullable=False)
    statement_end = Column(Date, nullable=False)
    ending_balance = Column(Numeric(12, 2), nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

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
    statement_id = Column(Integer, ForeignKey("bank_statements.id"), nullable=False, index=True)

    txn_date = Column(Date, nullable=False)
    description = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)

    matched = Column(Boolean, nullable=False, default=False)
    ledger_entry_id = Column(Integer, nullable=True)

    statement = relationship("BankStatement", back_populates="lines")


# =========================
# RECONCILIATION SUMMARY
# =========================
class Reconciliation(db.Model):
    __tablename__ = "reconciliations"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, nullable=False, index=True)
    account_code = Column(String, nullable=False, index=True)
    period = Column(String, nullable=False, index=True)

    ledger_balance = Column(Numeric(12, 2), nullable=False)
    statement_balance = Column(Numeric(12, 2), nullable=False)

    status = Column(
        Enum(ReconciliationStatus, name="reconciliation_status"),
        nullable=False,
        default=ReconciliationStatus.OPEN,
    )

    is_reconciled = Column(Boolean, nullable=False, default=False)
    finalized_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

# models.py  (FULL FILE — Bookkeeping Core, production-ready)

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Enum,
    Numeric,
    Boolean,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import relationship

from db import db

# =========================
# Core / Tenancy
# =========================

class Company(db.Model):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    users = relationship("User", back_populates="company", cascade="all, delete-orphan")
    accounts = relationship("ChartOfAccount", back_populates="company")
    periods = relationship("AccountingPeriod", back_populates="company")
    journals = relationship("Journal", back_populates="company")


class User(db.Model):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(Enum("owner", "admin", "accountant", name="user_role"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    company = relationship("Company", back_populates="users")

    __table_args__ = (
        UniqueConstraint("company_id", "email", name="uq_user_company_email"),
    )

# =========================
# Accounting Periods
# =========================

class AccountingPeriod(db.Model):
    __tablename__ = "accounting_periods"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    period = Column(String(7), nullable=False)  # YYYY-MM
    # CHECK constraint added in migration; validated at app layer before insert
    status = Column(Enum("open", "closed", "locked", name="period_status"), nullable=False, default="open")
    closed_at = Column(DateTime)
    locked_at = Column(DateTime)

    company = relationship("Company", back_populates="periods")
    journals = relationship("Journal", back_populates="period")

    __table_args__ = (
        UniqueConstraint("company_id", "period", name="uq_company_period"),
    )

# =========================
# Chart of Accounts
# =========================

class ChartOfAccount(db.Model):
    __tablename__ = "chart_of_accounts"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    account_code = Column(String(20), nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(
        Enum("asset", "liability", "equity", "revenue", "expense", name="account_type"),
        nullable=False,
    )
    normal_balance = Column(Enum("debit", "credit", name="normal_balance"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    company = relationship("Company", back_populates="accounts")
    lines = relationship("JournalLine", back_populates="account")

    __table_args__ = (
        UniqueConstraint("company_id", "account_code", name="uq_company_account_code"),
    )

# =========================
# Journals (Header)
# =========================

class Journal(db.Model):
    __tablename__ = "journals"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    period_id = Column(Integer, ForeignKey("accounting_periods.id"), nullable=False)
    source = Column(Enum("manual", "payroll", "system", name="journal_source"), nullable=False)
    reference_id = Column(String(255))
    description = Column(String(500))
    posted_by = Column(String(255))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    company = relationship("Company", back_populates="journals")
    period = relationship("AccountingPeriod", back_populates="journals")
    lines = relationship(
        "JournalLine",
        back_populates="journal",
        cascade="all, delete-orphan",
    )

# =========================
# Journal Lines (Double Entry)
# =========================

class JournalLine(db.Model):
    __tablename__ = "journal_lines"

    id = Column(Integer, primary_key=True)
    journal_id = Column(Integer, ForeignKey("journals.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("chart_of_accounts.id"), nullable=False)
    debit = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    credit = Column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)

    journal = relationship("Journal", back_populates="lines")
    account = relationship("ChartOfAccount", back_populates="lines")

    __table_args__ = (
        CheckConstraint(
            "(debit = 0 AND credit > 0) OR (credit = 0 AND debit > 0)",
            name="ck_debit_xor_credit",
        ),
    )

# =========================
# Ledger Balances (Derived / Cached)
# =========================

class LedgerBalance(db.Model):
    __tablename__ = "ledger_balances"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("chart_of_accounts.id"), nullable=False)
    period_id = Column(Integer, ForeignKey("accounting_periods.id"), nullable=False)
    ending_balance = Column(Numeric(14, 2), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "account_id", "period_id", name="uq_ledger_balance"),
    )

# =========================
# Reconciliations
# =========================

class Reconciliation(db.Model):
    __tablename__ = "reconciliations"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("chart_of_accounts.id"), nullable=False)
    period_id = Column(Integer, ForeignKey("accounting_periods.id"), nullable=False)
    statement_balance = Column(Numeric(14, 2), nullable=False)
    ledger_balance = Column(Numeric(14, 2), nullable=False)
    status = Column(Enum("open", "reconciled", name="reconciliation_status"), nullable=False, default="open")
    reconciled_at = Column(DateTime)

# =========================
# Audit Logs
# =========================

class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    entity = Column(String(100), nullable=False)
    entity_id = Column(Integer, nullable=False)
    action = Column(String(100), nullable=False)
    performed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    performed_by = Column(String(255))  # kept for legacy; prefer performed_by_user_id
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

# File: models/chart_of_accounts.py
# Purpose: Production-grade Chart of Accounts model + default COA seed template
# Status: Enterprise hardened
# Date: 2026-03-08

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db import db


ACCOUNT_TYPES = ("asset", "liability", "equity", "revenue", "expense")
NORMAL_BALANCES = ("debit", "credit")


class Account(db.Model):
    """
    Company-scoped Chart of Accounts.

    - account_code is the stable key used by ledger_entries.account_code
    - supports parent/child rollups
    - supports system and custom accounts
    """

    __tablename__ = "accounts"

    id = db.Column(Integer, primary_key=True, autoincrement=True)

    company_id = db.Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    account_code = db.Column(
        String(50),
        nullable=False,
        index=True,
    )

    name = db.Column(String(120), nullable=False)

    account_type = db.Column(
        Enum(*ACCOUNT_TYPES, name="account_type"),
        nullable=False,
    )

    normal_balance = db.Column(
        Enum(*NORMAL_BALANCES, name="normal_balance"),
        nullable=False,
    )

    parent_id = db.Column(
        Integer,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    is_active = db.Column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        default=True,
    )

    is_system = db.Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
    )

    created_at = db.Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    parent = relationship(
        "Account",
        remote_side=[id],
        backref="children",
        foreign_keys=[parent_id],
    )

    ledger_entries = relationship(
        "LedgerEntry",
        foreign_keys="LedgerEntry.account_id",
        lazy="select",
    )

    __table_args__ = (
        UniqueConstraint("company_id", "account_code", name="uq_accounts_company_code"),
        Index("ix_accounts_company_type", "company_id", "account_type"),
        Index("ix_accounts_parent_id", "parent_id"),
        CheckConstraint("length(account_code) > 0", name="ck_account_code_nonempty"),
        CheckConstraint("length(name) > 0", name="ck_account_name_nonempty"),
    )

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "account_code": self.account_code,
            "name": self.name,
            "account_type": self.account_type,
            "normal_balance": self.normal_balance,
            "parent_id": self.parent_id,
            "is_active": bool(self.is_active),
            "is_system": bool(self.is_system),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def default_coa_rows() -> list[dict]:
    """
    System-default accounts seeded per company during onboarding/migration.
    Includes trucking/payroll/tax-ready starter accounts.
    """
    return [
        # ASSETS
        {
            "account_code": "1000",
            "name": "Cash",
            "account_type": "asset",
            "normal_balance": "debit",
            "is_system": True,
            "is_active": True,
        },
        {
            "account_code": "1100",
            "name": "Accounts Receivable",
            "account_type": "asset",
            "normal_balance": "debit",
            "is_system": True,
            "is_active": True,
        },
        {
            "account_code": "1200",
            "name": "Prepaid Expenses",
            "account_type": "asset",
            "normal_balance": "debit",
            "is_system": True,
            "is_active": True,
        },
        {
            "account_code": "1300",
            "name": "Payroll Clearing",
            "account_type": "asset",
            "normal_balance": "debit",
            "is_system": True,
            "is_active": True,
        },

        # LIABILITIES
        {
            "account_code": "2000",
            "name": "Accounts Payable",
            "account_type": "liability",
            "normal_balance": "credit",
            "is_system": True,
            "is_active": True,
        },
        {
            "account_code": "2100",
            "name": "Payroll Payable",
            "account_type": "liability",
            "normal_balance": "credit",
            "is_system": True,
            "is_active": True,
        },
        {
            "account_code": "2110",
            "name": "Federal Withholding Payable",
            "account_type": "liability",
            "normal_balance": "credit",
            "is_system": True,
            "is_active": True,
        },
        {
            "account_code": "2120",
            "name": "State Withholding Payable",
            "account_type": "liability",
            "normal_balance": "credit",
            "is_system": True,
            "is_active": True,
        },
        {
            "account_code": "2130",
            "name": "FICA Payable (Employee)",
            "account_type": "liability",
            "normal_balance": "credit",
            "is_system": True,
            "is_active": True,
        },
        {
            "account_code": "2140",
            "name": "FICA Payable (Employer)",
            "account_type": "liability",
            "normal_balance": "credit",
            "is_system": True,
            "is_active": True,
        },
        {
            "account_code": "2150",
            "name": "FUTA Payable",
            "account_type": "liability",
            "normal_balance": "credit",
            "is_system": True,
            "is_active": True,
        },
        {
            "account_code": "2160",
            "name": "SUTA Payable",
            "account_type": "liability",
            "normal_balance": "credit",
            "is_system": True,
            "is_active": True,
        },
        {
            "account_code": "2170",
            "name": "Contractor Payable (1099)",
            "account_type": "liability",
            "normal_balance": "credit",
            "is_system": True,
            "is_active": True,
        },

        # EQUITY
        {
            "account_code": "3000",
            "name": "Owner's Equity",
            "account_type": "equity",
            "normal_balance": "credit",
            "is_system": True,
            "is_active": True,
        },
        {
            "account_code": "3100",
            "name": "Retained Earnings",
            "account_type": "equity",
            "normal_balance": "credit",
            "is_system": True,
            "is_active": True,
        },

        # REVENUE
        {
            "account_code": "4000",
            "name": "Operating Revenue",
            "account_type": "revenue",
            "normal_balance": "credit",
            "is_system": True,
            "is_active": True,
        },

        # EXPENSES
        {
            "account_code": "5000",
            "name": "Wages Expense",
            "account_type": "expense",
            "normal_balance": "debit",
            "is_system": True,
            "is_active": True,
        },
        {
            "account_code": "5010",
            "name": "Contract Labor Expense",
            "account_type": "expense",
            "normal_balance": "debit",
            "is_system": True,
            "is_active": True,
        },
        {
            "account_code": "5100",
            "name": "Payroll Tax Expense (Employer)",
            "account_type": "expense",
            "normal_balance": "debit",
            "is_system": True,
            "is_active": True,
        },
        {
            "account_code": "5200",
            "name": "Bank Fees",
            "account_type": "expense",
            "normal_balance": "debit",
            "is_system": True,
            "is_active": True,
        },
    ]


# Alias for code that expects ChartOfAccount (canonical model name is Account)
ChartOfAccount = Account

__all__ = ["Account", "ChartOfAccount", "default_coa_rows"]

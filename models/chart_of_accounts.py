# freightpay/models/chart_of_accounts.py
# PRODUCTION GRADE CHART OF ACCOUNTS (COA) — tenant/company-scoped, payroll-ready

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    String,
    Boolean,
    ForeignKey,
    Enum,
    UniqueConstraint,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class Account(Base):
    """
    Company-scoped Chart of Accounts.

    - account_code is the stable key used by the Ledger (ledger_entries.account_code)
    - supports parent/child rollups
    - supports system accounts (protected) + custom accounts
    """

    __tablename__ = "accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Stable key referenced by LedgerEntry.account_code
    account_code = Column(String(50), nullable=False)

    name = Column(String(120), nullable=False)

    account_type = Column(
        Enum(
            "asset",
            "liability",
            "equity",
            "revenue",
            "expense",
            name="account_type",
        ),
        nullable=False,
    )

    normal_balance = Column(
        Enum("debit", "credit", name="normal_balance"),
        nullable=False,
    )

    parent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    is_active = Column(Boolean, nullable=False, default=True)
    is_system = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    company = relationship("Company", backref="accounts")
    parent = relationship("Account", remote_side=[id], backref="children")

    __table_args__ = (
        UniqueConstraint("company_id", "account_code", name="uq_accounts_company_code"),
        Index("ix_accounts_company_type", "company_id", "account_type"),
        CheckConstraint("length(account_code) > 0", name="ck_account_code_nonempty"),
        CheckConstraint("length(name) > 0", name="ck_account_name_nonempty"),
    )

    def as_dict(self) -> dict:
        return {
            "id": str(self.id),
            "company_id": str(self.company_id),
            "account_code": self.account_code,
            "name": self.name,
            "account_type": self.account_type,
            "normal_balance": self.normal_balance,
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "is_active": self.is_active,
            "is_system": self.is_system,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def default_coa_rows() -> list[dict]:
    """
    System-default accounts (payroll + tax ready).
    Seed these per company during onboarding/migration.
    """
    return [
        # ASSETS
        {"account_code": "1000", "name": "Cash", "account_type": "asset", "normal_balance": "debit"},
        {"account_code": "1100", "name": "Accounts Receivable", "account_type": "asset", "normal_balance": "debit"},
        {"account_code": "1200", "name": "Prepaid Expenses", "account_type": "asset", "normal_balance": "debit"},
        {"account_code": "1300", "name": "Payroll Clearing", "account_type": "asset", "normal_balance": "debit"},

        # LIABILITIES
        {"account_code": "2000", "name": "Accounts Payable", "account_type": "liability", "normal_balance": "credit"},
        {"account_code": "2100", "name": "Payroll Payable", "account_type": "liability", "normal_balance": "credit"},
        {"account_code": "2110", "name": "Federal Withholding Payable", "account_type": "liability", "normal_balance": "credit"},
        {"account_code": "2120", "name": "State Withholding Payable", "account_type": "liability", "normal_balance": "credit"},
        {"account_code": "2130", "name": "FICA Payable (Employee)", "account_type": "liability", "normal_balance": "credit"},
        {"account_code": "2140", "name": "FICA Payable (Employer)", "account_type": "liability", "normal_balance": "credit"},
        {"account_code": "2150", "name": "FUTA Payable", "account_type": "liability", "normal_balance": "credit"},
        {"account_code": "2160", "name": "SUTA Payable", "account_type": "liability", "normal_balance": "credit"},
        {"account_code": "2170", "name": "Contractor Payable (1099)", "account_type": "liability", "normal_balance": "credit"},

        # EQUITY
        {"account_code": "3000", "name": "Owner's Equity", "account_type": "equity", "normal_balance": "credit"},
        {"account_code": "3100", "name": "Retained Earnings", "account_type": "equity", "normal_balance": "credit"},

        # REVENUE
        {"account_code": "4000", "name": "Operating Revenue", "account_type": "revenue", "normal_balance": "credit"},

        # EXPENSES
        {"account_code": "5000", "name": "Wages Expense", "account_type": "expense", "normal_balance": "debit"},
        {"account_code": "5010", "name": "Contract Labor Expense", "account_type": "expense", "normal_balance": "debit"},
        {"account_code": "5100", "name": "Payroll Tax Expense (Employer)", "account_type": "expense", "normal_balance": "debit"},
        {"account_code": "5200", "name": "Bank Fees", "account_type": "expense", "normal_balance": "debit"},
    ]


# Commit message: Add company-scoped Chart of Accounts model + default payroll-ready COA seed list

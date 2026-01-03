# freightpay/models/bank_accounts.py
# BANK ACCOUNTS + FEED INGESTION (PLAID-STYLE FOUNDATION)

import uuid
from decimal import Decimal

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    String,
    Boolean,
    ForeignKey,
    Numeric,
    Enum,
    UniqueConstraint,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    provider = Column(
        Enum("plaid", "manual", name="bank_provider"),
        nullable=False,
    )

    provider_account_id = Column(String(120), nullable=True)

    name = Column(String(120), nullable=False)
    institution = Column(String(120), nullable=True)

    account_type = Column(
        Enum("checking", "savings", "credit_card", name="bank_account_type"),
        nullable=False,
    )

    currency = Column(String(3), nullable=False, default="USD")
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    company = relationship("Company", backref="bank_accounts")

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "provider",
            "provider_account_id",
            name="uq_bank_account_provider",
        ),
        Index("ix_bank_accounts_company", "company_id"),
    )


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    bank_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bank_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    transaction_date = Column(Date, nullable=False)
    description = Column(String(255), nullable=False)

    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")

    is_posted = Column(Boolean, nullable=False, default=False)

    journal_id = Column(
        UUID(as_uuid=True),
        ForeignKey("journals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    bank_account = relationship("BankAccount", backref="transactions")
    journal = relationship("Journal", backref="bank_transactions")

    __table_args__ = (
        CheckConstraint("amount != 0", name="ck_bank_txn_amount_nonzero"),
        Index("ix_bank_txn_account_date", "bank_account_id", "transaction_date"),
    )

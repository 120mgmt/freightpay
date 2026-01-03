# freightpay/models/bank_accounts.py
# STRIPE FINANCIAL CONNECTIONS — BANK FEED INGESTION (PRODUCTION)

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
        Enum("stripe", "manual", name="bank_provider"),
        nullable=False,
        default="stripe",
    )

    # Stripe Financial Connections IDs
    stripe_account_id = Column(String(120), nullable=True)   # fa_*
    stripe_institution = Column(String(120), nullable=True)

    name = Column(String(120), nullable=False)

    account_type = Column(
        Enum(
            "checking",
            "savings",
            "credit_card",
            name="bank_account_type",
        ),
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
            "stripe_account_id",
            name="uq_bank_account_stripe",
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

    # Stripe Financial Connections Transaction ID
    stripe_transaction_id = Column(String(120), nullable=True, index=True)

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
        UniqueConstraint(
            "bank_account_id",
            "stripe_transaction_id",
            name="uq_bank_txn_stripe_id",
        ),
        Index("ix_bank_txn_account_date", "bank_account_id", "transaction_date"),
    )

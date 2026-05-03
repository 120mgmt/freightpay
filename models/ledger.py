# File: models/ledger.py
# Purpose: Canonical accounting journal + immutable ledger models
# Status: Enterprise hardened
# Date: 2026-03-08

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db import db


class Journal(db.Model):

    __tablename__ = "journals"

    id = db.Column(BigInteger, primary_key=True, autoincrement=True)

    company_id = db.Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_type = db.Column(String(32), nullable=False)
    source_id = db.Column(String(64), nullable=False)

    accounting_period = db.Column(
        String(7),
        nullable=False,
        index=True,
    )

    description = db.Column(String(255), nullable=False)

    posted_at = db.Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    posted_by = db.Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    is_reversal = db.Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
    )

    reversed_journal_id = db.Column(
        BigInteger,
        ForeignKey("journals.id", ondelete="SET NULL"),
        nullable=True,
    )

    entries = relationship(
        "LedgerEntry",
        back_populates="journal",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="LedgerEntry.journal_id",
    )

    reversal_of = relationship(
        "Journal",
        remote_side=[id],
        foreign_keys=[reversed_journal_id],
        uselist=False,
    )

    __table_args__ = (
        Index("ix_journals_company_period", "company_id", "accounting_period"),
        Index("ix_journals_company_source", "company_id", "source_type", "source_id"),
    )

    def as_dict(self) -> dict:
        return {
            "id": int(self.id) if self.id else None,
            "company_id": self.company_id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "accounting_period": self.accounting_period,
            "description": self.description,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "posted_by": self.posted_by,
            "is_reversal": bool(self.is_reversal),
            "reversed_journal_id": (
                int(self.reversed_journal_id)
                if self.reversed_journal_id
                else None
            ),
        }


class LedgerEntry(db.Model):

    __tablename__ = "ledger_entries"

    id = db.Column(BigInteger, primary_key=True, autoincrement=True)

    company_id = db.Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    journal_id = db.Column(
        BigInteger,
        ForeignKey("journals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    account_id = db.Column(
        Integer,
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    account_code = db.Column(
        String(50),
        nullable=False,
    )

    debit = db.Column(
        Numeric(14, 2),
        nullable=False,
        server_default=text("0.00"),
        default=Decimal("0.00"),
    )

    credit = db.Column(
        Numeric(14, 2),
        nullable=False,
        server_default=text("0.00"),
        default=Decimal("0.00"),
    )

    currency = db.Column(
        String(3),
        nullable=False,
        server_default=text("'USD'"),
        default="USD",
    )

    memo = db.Column(String(255), nullable=True)

    created_at = db.Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    journal = relationship(
        "Journal",
        back_populates="entries",
        foreign_keys=[journal_id],
    )

    account = relationship(
        "Account",
        foreign_keys=[account_id],
        lazy="joined",
    )

    __table_args__ = (
        CheckConstraint(
            "(debit = 0 AND credit > 0) OR (credit = 0 AND debit > 0)",
            name="ck_ledger_debit_credit_exclusive",
        ),
        CheckConstraint(
            "debit >= 0 AND credit >= 0",
            name="ck_ledger_non_negative_amounts",
        ),
        Index("ix_ledger_company_account", "company_id", "account_id"),
        Index("ix_ledger_company_journal", "company_id", "journal_id"),
        Index("ix_ledger_company_created", "company_id", "created_at"),
    )

    def as_dict(self) -> dict:
        return {
            "id": int(self.id) if self.id else None,
            "company_id": self.company_id,
            "journal_id": int(self.journal_id) if self.journal_id else None,
            "account_id": self.account_id,
            "account_code": self.account_code,
            "debit": str(self.debit),
            "credit": str(self.credit),
            "currency": self.currency,
            "memo": self.memo,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


__all__ = ["Journal", "LedgerEntry"]

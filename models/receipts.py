# freightpay/models/receipts.py
# RECEIPTS + EXPENSE CAPTURE (supports attachments + line items + posting-ready status)

import uuid
from decimal import Decimal

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    String,
    ForeignKey,
    Numeric,
    Enum,
    CheckConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = Column(
        Enum(
            "uploaded",    # file stored, metadata optional
            "categorized", # vendor/date/amount/account chosen
            "posted",      # journal posted to ledger
            "voided",      # reversed/voided with audit trail at service layer
            name="receipt_status",
        ),
        nullable=False,
        default="uploaded",
    )

    vendor = Column(String(160), nullable=True)
    receipt_date = Column(Date, nullable=True)

    subtotal = Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    tax = Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    tip = Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    total = Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    currency = Column(String(3), nullable=False, default="USD")

    # Accounting categorization (maps to COA Account.account_code)
    expense_account_code = Column(String(50), nullable=True)
    payment_account_code = Column(String(50), nullable=True)  # typically Cash/Bank/Credit Card

    notes = Column(String(500), nullable=True)

    # File storage references (S3/R2/etc handled by upload service)
    file_url = Column(String(500), nullable=False)
    file_mime = Column(String(100), nullable=True)
    file_sha256 = Column(String(64), nullable=True)

    # Link to posted journal for traceability
    journal_id = Column(
        UUID(as_uuid=True),
        ForeignKey("journals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_by = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    items = relationship(
        "ReceiptItem",
        back_populates="receipt",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="ck_receipt_subtotal_nonneg"),
        CheckConstraint("tax >= 0", name="ck_receipt_tax_nonneg"),
        CheckConstraint("tip >= 0", name="ck_receipt_tip_nonneg"),
        CheckConstraint("total >= 0", name="ck_receipt_total_nonneg"),
        Index("ix_receipts_company_status", "company_id", "status"),
        Index("ix_receipts_company_date", "company_id", "receipt_date"),
    )

    def as_dict(self) -> dict:
        return {
            "id": str(self.id),
            "company_id": str(self.company_id),
            "status": self.status,
            "vendor": self.vendor,
            "receipt_date": self.receipt_date.isoformat() if self.receipt_date else None,
            "subtotal": float(self.subtotal),
            "tax": float(self.tax),
            "tip": float(self.tip),
            "total": float(self.total),
            "currency": self.currency,
            "expense_account_code": self.expense_account_code,
            "payment_account_code": self.payment_account_code,
            "notes": self.notes,
            "file_url": self.file_url,
            "file_mime": self.file_mime,
            "file_sha256": self.file_sha256,
            "journal_id": str(self.journal_id) if self.journal_id else None,
            "created_by": str(self.created_by),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [i.as_dict() for i in (self.items or [])],
        }


class ReceiptItem(Base):
    __tablename__ = "receipt_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    receipt_id = Column(
        UUID(as_uuid=True),
        ForeignKey("receipts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    description = Column(String(255), nullable=False)
    quantity = Column(Numeric(12, 3), nullable=False, default=Decimal("1.000"))
    unit_price = Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    line_total = Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    # Optional per-line account override
    account_code = Column(String(50), nullable=True)

    receipt = relationship("Receipt", back_populates="items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_receipt_item_qty_positive"),
        CheckConstraint("unit_price >= 0", name="ck_receipt_item_unit_price_nonneg"),
        CheckConstraint("line_total >= 0", name="ck_receipt_item_line_total_nonneg"),
        Index("ix_receipt_items_receipt", "receipt_id"),
    )

    def as_dict(self) -> dict:
        return {
            "id": str(self.id),
            "receipt_id": str(self.receipt_id),
            "description": self.description,
            "quantity": float(self.quantity),
            "unit_price": float(self.unit_price),
            "line_total": float(self.line_total),
            "account_code": self.account_code,
        }

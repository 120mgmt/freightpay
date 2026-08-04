# File: models/client_invoice.py
# Purpose: Invoices a company sends to ITS OWN clients (brokers, shippers) for
#          services rendered — not to be confused with models/invoice.py, which
#          models Stripe's subscription invoices for LedgerHaul's own billing.

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from db import db

INVOICE_STATUSES = ("draft", "sent", "paid", "void")


def _money(value: Any) -> str:
    return "0.00" if value is None else str(value)


class ClientInvoice(db.Model):
    __tablename__ = "client_invoices"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)

    # Per-company sequence, e.g. INV-1001.
    invoice_number = db.Column(db.String(40), nullable=False)

    # =========================
    # WHO IS BEING BILLED
    # =========================
    client_name = db.Column(db.String(255), nullable=False)
    client_email = db.Column(db.String(255), nullable=True)
    client_address = db.Column(db.Text, nullable=True)

    # =========================
    # DATES / STATUS
    # =========================
    issue_date = db.Column(db.Date, nullable=False, default=lambda: datetime.now(timezone.utc).date())
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="draft", server_default="draft", index=True)

    # =========================
    # MONEY
    # =========================
    currency = db.Column(db.String(3), nullable=False, default="USD", server_default="USD")
    subtotal = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    tax = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    total = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    amount_paid = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    notes = db.Column(db.Text, nullable=True)

    # =========================
    # STRIPE PAYMENT LINK
    # =========================
    stripe_payment_link_id = db.Column(db.String(255), nullable=True)
    stripe_payment_link_url = db.Column(db.String(500), nullable=True)

    # Journal that recognised this invoice's revenue once paid. Storing it
    # keeps the posting idempotent and makes it reversible on void.
    journal_id = db.Column(db.BigInteger, nullable=True)

    # =========================
    # LIFECYCLE
    # =========================
    sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    paid_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_by_user_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    items = db.relationship(
        "ClientInvoiceItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="ClientInvoiceItem.sort_order",
    )

    __table_args__ = (
        UniqueConstraint("company_id", "invoice_number", name="uq_client_invoices_company_number"),
        CheckConstraint("total >= 0", name="ck_client_invoices_total_nonneg"),
        Index("ix_client_invoices_company_status", "company_id", "status"),
    )

    @property
    def balance_due(self) -> Decimal:
        return (self.total or Decimal("0.00")) - (self.amount_paid or Decimal("0.00"))

    @property
    def is_overdue(self) -> bool:
        if self.status != "sent" or not self.due_date:
            return False
        return self.due_date < date.today()

    def to_dict(self, with_items: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "company_id": self.company_id,
            "invoice_number": self.invoice_number,
            "client_name": self.client_name,
            "client_email": self.client_email,
            "client_address": self.client_address,
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "status": self.status,
            "is_overdue": self.is_overdue,
            "currency": self.currency,
            "subtotal": _money(self.subtotal),
            "tax": _money(self.tax),
            "total": _money(self.total),
            "amount_paid": _money(self.amount_paid),
            "balance_due": _money(self.balance_due),
            "notes": self.notes,
            "payment_link_url": self.stripe_payment_link_url,
            "posted_to_books": self.journal_id is not None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if with_items:
            data["items"] = [i.to_dict() for i in self.items]
        return data


class ClientInvoiceItem(db.Model):
    __tablename__ = "client_invoice_items"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(
        db.Integer,
        db.ForeignKey("client_invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description = db.Column(db.String(500), nullable=False)
    quantity = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("1.00"))
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    invoice = db.relationship("ClientInvoice", back_populates="items")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "quantity": _money(self.quantity),
            "unit_price": _money(self.unit_price),
            "amount": _money(self.amount),
            "sort_order": self.sort_order,
        }


__all__ = ["ClientInvoice", "ClientInvoiceItem", "INVOICE_STATUSES"]

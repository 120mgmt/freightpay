# freightpay/services/receipt_journalization.py
# RECEIPT → LEDGER JOURNALIZATION (expense posting, compliance-safe)

from decimal import Decimal
from sqlalchemy.orm import Session

from models.receipts import Receipt
from services.ledger_posting_guard import post_journal, LedgerPostingError


def post_receipt(
    db: Session,
    *,
    receipt_id,
    company_id,
    accounting_period: str,
    posted_by,
):
    """
    Posts a receipt as an expense journal entry.

    Requirements:
    - Receipt must be categorized
    - expense_account_code and payment_account_code must be set
    - total must equal subtotal + tax + tip
    """

    receipt = (
        db.query(Receipt)
        .filter(
            Receipt.id == receipt_id,
            Receipt.company_id == company_id,
        )
        .one_or_none()
    )

    if not receipt:
        raise LedgerPostingError("Receipt not found")

    if receipt.status != "categorized":
        raise LedgerPostingError("Receipt is not ready to post")

    if not receipt.expense_account_code or not receipt.payment_account_code:
        raise LedgerPostingError("Receipt missing account codes")

    expected_total = (
        Decimal(receipt.subtotal)
        + Decimal(receipt.tax)
        + Decimal(receipt.tip)
    )

    if Decimal(receipt.total) != expected_total:
        raise LedgerPostingError("Receipt totals do not reconcile")

    entries = [
        {
            # Expense
            "account_code": receipt.expense_account_code,
            "debit": Decimal(receipt.total),
            "credit": Decimal("0.00"),
        },
        {
            # Cash / Bank / Card
            "account_code": receipt.payment_account_code,
            "debit": Decimal("0.00"),
            "credit": Decimal(receipt.total),
        },
    ]

    journal_id = post_journal(
        db,
        company_id=company_id,
        source_type="expense",
        source_id=receipt.id,
        accounting_period=accounting_period,
        description=f"Receipt expense: {receipt.vendor or 'Unknown'}",
        posted_by=posted_by,
        entries=entries,
    )

    receipt.status = "posted"
    receipt.journal_id = journal_id

    db.commit()
    return journal_id

# freightpay/services/bank_transaction_posting.py
# BANK TRANSACTION → JOURNAL → LEDGER (supports auto-categorization + review gate)

from __future__ import annotations

from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.bank_accounts import BankTransaction, BankAccount
from models.categorization_rules import CategorizationRule
from services.ledger_posting_guard import post_journal


class BankPostingError(Exception):
    pass


def _apply_rules(
    db: Session,
    *,
    company_id,
    description: str,
) -> tuple[str | None, bool]:
    """
    Returns (expense_account_code, review_required)
    First-match wins, ordered by created_at.
    """
    stmt = (
        select(CategorizationRule)
        .where(
            CategorizationRule.company_id == company_id,
            CategorizationRule.is_active.is_(True),
            CategorizationRule.applies_to.in_(["bank", "both"]),
        )
        .order_by(CategorizationRule.created_at.asc())
    )
    rules = db.execute(stmt).scalars().all()

    desc = (description or "").strip()

    for r in rules:
        val = (r.match_value or "").strip()

        if r.match_type == "contains" and val.lower() in desc.lower():
            return r.expense_account_code, bool(r.review_required)
        if r.match_type == "equals" and desc.lower() == val.lower():
            return r.expense_account_code, bool(r.review_required)
        if r.match_type == "starts_with" and desc.lower().startswith(val.lower()):
            return r.expense_account_code, bool(r.review_required)
        if r.match_type == "ends_with" and desc.lower().endswith(val.lower()):
            return r.expense_account_code, bool(r.review_required)

        # regex support intentionally deferred to avoid unsafe patterns in v1

    return None, True  # default: require review


def post_bank_transaction(
    db: Session,
    *,
    company_id,
    bank_transaction_id,
    accounting_period: str,
    posted_by,
    cash_account_code: str = "1000",
):
    """
    Posts an expense-type bank transaction:

      DR expense_account_code
      CR cash_account_code

    Requires:
    - BankTransaction belongs to company via BankAccount
    - Not already posted
    - Categorization rule match OR manual categorization (v2)
    """

    stmt = (
        select(BankTransaction)
        .join(BankAccount, BankAccount.id == BankTransaction.bank_account_id)
        .where(
            BankTransaction.id == bank_transaction_id,
            BankAccount.company_id == company_id,
        )
    )
    tx = db.execute(stmt).scalar_one_or_none()

    if not tx:
        raise BankPostingError("Bank transaction not found")

    if tx.is_posted or tx.journal_id is not None:
        raise BankPostingError("Bank transaction already posted")

    expense_account_code, review_required = _apply_rules(
        db,
        company_id=company_id,
        description=tx.description,
    )

    if review_required or not expense_account_code:
        raise BankPostingError("Bank transaction requires review/categorization")

    amt = Decimal(str(tx.amount))
    if amt == 0:
        raise BankPostingError("Amount cannot be zero")

    # Convention:
    # Negative amount = money out (expense)
    # Positive amount = money in (income) — v2 will support revenue posting
    if amt > 0:
        raise BankPostingError("Positive (income) bank transactions not supported in v1 posting")

    amt_abs = abs(amt)

    journal_id = post_journal(
        db,
        company_id=company_id,
        source_type="payment",
        source_id=bank_transaction_id,
        accounting_period=accounting_period,
        description=f"Bank txn {bank_transaction_id}: {tx.description}",
        posted_by=posted_by,
        entries=[
            {"account_code": expense_account_code, "debit": amt_abs, "credit": Decimal("0.00")},
            {"account_code": cash_account_code, "debit": Decimal("0.00"), "credit": amt_abs},
        ],
    )

    tx.journal_id = journal_id
    tx.is_posted = True
    db.add(tx)
    db.commit()

    return journal_id

# freightpay/services/ledger_posting_guard.py
# COMPLIANCE ENFORCEMENT — single gate for ALL ledger postings

from sqlalchemy.orm import Session
from sqlalchemy import func
from decimal import Decimal

from freightpay.models.accounting_periods import AccountingPeriod
from freightpay.models.ledger import Journal, LedgerEntry


class LedgerPostingError(Exception):
    pass


def assert_period_open(
    db: Session,
    *,
    company_id,
    accounting_period: str,
):
    period = (
        db.query(AccountingPeriod)
        .filter(
            AccountingPeriod.company_id == company_id,
            AccountingPeriod.period_code == accounting_period,
        )
        .one_or_none()
    )

    if not period:
        raise LedgerPostingError("Accounting period does not exist")

    if period.is_hard_locked:
        raise LedgerPostingError("Accounting period is hard locked")

    if period.is_closed:
        raise LedgerPostingError("Accounting period is closed")

    return period


def assert_double_entry(entries: list[dict]):
    debit_total = Decimal("0.00")
    credit_total = Decimal("0.00")

    for e in entries:
        debit_total += Decimal(e.get("debit", 0))
        credit_total += Decimal(e.get("credit", 0))

    if debit_total != credit_total:
        raise LedgerPostingError("Debits do not equal credits")


def post_journal(
    db: Session,
    *,
    company_id,
    source_type: str,
    source_id,
    accounting_period: str,
    description: str,
    posted_by,
    entries: list[dict],
):
    """
    ONLY approved path to write to the ledger.
    """

    assert_period_open(
        db,
        company_id=company_id,
        accounting_period=accounting_period,
    )

    assert_double_entry(entries)

    journal = Journal(
        company_id=company_id,
        source_type=source_type,
        source_id=source_id,
        accounting_period=accounting_period,
        description=description,
        posted_by=posted_by,
    )

    db.add(journal)
    db.flush()  # obtain journal.id

    for e in entries:
        line = LedgerEntry(
            company_id=company_id,
            journal_id=journal.id,
            account_code=e["account_code"],
            debit=e.get("debit", Decimal("0.00")),
            credit=e.get("credit", Decimal("0.00")),
            currency=e.get("currency", "USD"),
        )
        db.add(line)

    db.commit()
    return journal.id

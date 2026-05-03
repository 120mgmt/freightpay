# freightpay/services/ledger_posting_guard.py
# COMPLIANCE ENFORCEMENT — single gate for ALL ledger postings

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from models.periods import AccountingPeriod
from models.chart_of_accounts import Account
from models.ledger import Journal, LedgerEntry


_Q2 = Decimal("0.01")


class LedgerPostingError(Exception):
    pass


def _to_decimal(value) -> Decimal:
    try:
        return Decimal(str(value or "0")).quantize(_Q2, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise LedgerPostingError(f"Invalid decimal value: {value}") from exc


def _resolve_account_id(db: Session, company_id: int, account_code: str) -> int:
    """Resolve account_code to Account.id for the company; raise if not found."""
    row = (
        db.execute(
            select(Account).where(
                Account.company_id == company_id,
                Account.account_code == account_code,
                Account.is_active.is_(True),
            )
        ).scalar_one_or_none()
    )
    if not row:
        raise LedgerPostingError(
            f"Account not found: company_id={company_id}, account_code={account_code}"
        )
    return row.id


def assert_period_open(
    db: Session,
    *,
    company_id,
    accounting_period: str,
):
    period = (
        db.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.company_id == company_id,
                AccountingPeriod.period == accounting_period,
            )
        ).scalar_one_or_none()
    )

    if not period:
        raise LedgerPostingError("Accounting period does not exist")

    if getattr(period, "is_hard_locked", False):
        raise LedgerPostingError("Accounting period is hard locked")

    if period.is_closed:
        raise LedgerPostingError("Accounting period is closed")

    return period


def assert_double_entry(entries: list[dict]):
    debit_total = Decimal("0.00")
    credit_total = Decimal("0.00")

    for e in entries:
        debit_total += _to_decimal(e.get("debit", 0))
        credit_total += _to_decimal(e.get("credit", 0))

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

    if not entries or not isinstance(entries, list):
        raise LedgerPostingError("Entries are required")

    assert_period_open(
        db,
        company_id=company_id,
        accounting_period=accounting_period,
    )

    assert_double_entry(entries)

    try:
        journal = Journal(
            company_id=company_id,
            source_type=source_type,
            source_id=str(source_id),
            accounting_period=accounting_period,
            description=description,
            posted_by=posted_by,
        )

        db.add(journal)
        db.flush()  # obtain journal.id

        for e in entries:
            acct_code = str(e["account_code"]).strip()
            if not acct_code:
                raise LedgerPostingError("account_code is required for all ledger entries")

            account_id = _resolve_account_id(db, company_id, acct_code)

            line = LedgerEntry(
                company_id=company_id,
                journal_id=journal.id,
                account_id=account_id,
                account_code=acct_code,
                debit=_to_decimal(e.get("debit", Decimal("0.00"))),
                credit=_to_decimal(e.get("credit", Decimal("0.00"))),
                currency=str(e.get("currency", "USD")).strip() or "USD",
            )
            db.add(line)

        db.commit()
        return journal.id

    except (LedgerPostingError, SQLAlchemyError) as exc:
        db.rollback()
        if isinstance(exc, LedgerPostingError):
            raise
        raise LedgerPostingError(f"Ledger posting failed: {str(exc)}") from exc

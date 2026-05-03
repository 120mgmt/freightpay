# services/journal_posting.py  (FULL FILE — atomic double-entry enforcement)

from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import (
    AccountingPeriod,
    Account,
    Journal,
    LedgerEntry,
)
from db import db


class JournalPostingError(Exception):
    pass


def _validate_journal_lines(lines: list) -> None:
    """
    Application-layer guard: reject zero-value lines before they reach DB.
    Prevents ghost lines that could corrupt ledger balances if DB constraint is bypassed.
    """
    for i, line in enumerate(lines):
        debit = float(line.get("debit", 0) or 0)
        credit = float(line.get("credit", 0) or 0)
        if debit == 0 and credit == 0:
            raise JournalPostingError(
                f"Journal line {i} has zero debit and zero credit — "
                "at least one must be non-zero."
            )
        if debit != 0 and credit != 0:
            raise JournalPostingError(
                f"Journal line {i} has both debit ({debit}) and credit ({credit}) set — "
                "only one must be non-zero (double-entry constraint)."
            )


def post_journal(
    *,
    company_id: int,
    period_id: int,
    source: str,
    description: str,
    lines: list[dict],
    posted_by: str | None = None,
    reference_id: str | None = None,
) -> Journal:
    """
    lines = [
        {"account_code": "5000", "debit": "100.00", "credit": "0.00"},
        {"account_code": "1000", "debit": "0.00", "credit": "100.00"},
    ]
    """

    if not lines or len(lines) < 2:
        raise JournalPostingError("Journal must have at least two lines")

    session: Session = db.session

    # --- Period enforcement ---
    period = (
        session.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.id == period_id,
                AccountingPeriod.company_id == company_id,
            )
        ).scalar_one_or_none()
    )
    if not period:
        raise JournalPostingError("Accounting period not found")

    if period.is_closed or getattr(period, "status", None) in ("closed", "locked"):
        raise JournalPostingError("Cannot post into closed or locked period")

    # --- Build journal (canonical models/ledger: accounting_period, source_type, source_id) ---
    journal = Journal(
        company_id=company_id,
        source_type=source,
        source_id=reference_id or str(period_id),
        accounting_period=period.period,
        description=description,
        posted_by=posted_by,
    )
    session.add(journal)
    session.flush()  # get journal.id

    total_debits = Decimal("0.00")
    total_credits = Decimal("0.00")

    for line in lines:
        acct_code = line.get("account_code")
        debit = Decimal(str(line.get("debit", "0.00")))
        credit = Decimal(str(line.get("credit", "0.00")))

        if debit > 0 and credit > 0:
            raise JournalPostingError("Line cannot have both debit and credit")

        if debit == 0 and credit == 0:
            raise JournalPostingError("Line must have a debit or credit")

        account = (
            session.execute(
                select(Account).where(
                    Account.company_id == company_id,
                    Account.account_code == acct_code,
                    Account.is_active.is_(True),
                )
            ).scalar_one_or_none()
        )
        if not account:
            raise JournalPostingError(f"Invalid account code: {acct_code}")

        entry = LedgerEntry(
            company_id=company_id,
            journal_id=journal.id,
            account_id=account.id,
            account_code=acct_code,
            debit=debit,
            credit=credit,
        )
        session.add(entry)

        total_debits += debit
        total_credits += credit

    if total_debits != total_credits:
        raise JournalPostingError(
            f"Journal out of balance: debits {total_debits} ≠ credits {total_credits}"
        )

    session.commit()
    return journal
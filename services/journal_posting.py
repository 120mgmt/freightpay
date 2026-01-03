# services/journal_posting.py  (FULL FILE — atomic double-entry enforcement)

from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import (
    AccountingPeriod,
    ChartOfAccount,
    Journal,
    JournalLine,
)
from db import db


class JournalPostingError(Exception):
    pass


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
        session.query(AccountingPeriod)
        .filter_by(id=period_id, company_id=company_id)
        .one_or_none()
    )
    if not period:
        raise JournalPostingError("Accounting period not found")

    if period.status in ("closed", "locked"):
        raise JournalPostingError("Cannot post into closed or locked period")

    # --- Build journal ---
    journal = Journal(
        company_id=company_id,
        period_id=period_id,
        source=source,
        description=description,
        posted_by=posted_by,
        reference_id=reference_id,
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
            session.query(ChartOfAccount)
            .filter_by(company_id=company_id, account_code=acct_code, is_active=True)
            .one_or_none()
        )
        if not account:
            raise JournalPostingError(f"Invalid account code: {acct_code}")

        jl = JournalLine(
            journal_id=journal.id,
            account_id=account.id,
            debit=debit,
            credit=credit,
        )
        session.add(jl)

        total_debits += debit
        total_credits += credit

    if total_debits != total_credits:
        raise JournalPostingError(
            f"Journal out of balance: debits {total_debits} ≠ credits {total_credits}"
        )

    session.commit()
    return journal

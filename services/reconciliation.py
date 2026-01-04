# services/reconciliation.py
# FULL FILE — reconciliation engine (ledger ↔ statement) — ROOT IMPORTS

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from db import db
from models.reconciliation import BankStatement, ReconciliationStatus
from models.ledger import LedgerEntry
from models.periods import AccountingPeriod


class ReconciliationError(Exception):
    pass


def _as_decimal(v) -> Decimal:
    if v is None:
        return Decimal("0.00")
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def compute_ledger_balance(
    *,
    company_id,
    account_code: str,
    period: str,
) -> Decimal:
    """
    Ledger cash balance for an account up to and including a period (YYYY-MM).
    Assumes LedgerEntry.period exists and is stored as YYYY-MM.
    """
    session: Session = db.session

    debit_sum = func.coalesce(func.sum(LedgerEntry.debit), 0)
    credit_sum = func.coalesce(func.sum(LedgerEntry.credit), 0)

    row = (
        session.query(debit_sum.label("debits"), credit_sum.label("credits"))
        .filter(
            LedgerEntry.company_id == company_id,
            LedgerEntry.account_code == account_code,
            LedgerEntry.period <= period,
        )
        .one()
    )

    bal = _as_decimal(row.debits) - _as_decimal(row.credits)
    return bal.quantize(Decimal("0.01"))


def match_statement_lines(*, statement_id: int) -> None:
    """
    Auto-match statement lines to ledger entries by exact amount within the same period/account.
    Marks statement lines as matched and stores matched journal_id when found.
    """
    session: Session = db.session

    stmt = session.query(BankStatement).filter_by(id=statement_id).one_or_none()
    if not stmt:
        raise ReconciliationError("Statement not found")

    # Pull ledger entries for this account/period
    ledger_rows = (
        session.query(LedgerEntry)
        .filter(
            LedgerEntry.company_id == stmt.company_id,
            LedgerEntry.account_code == stmt.account_code,
            LedgerEntry.period == stmt.period,
        )
        .all()
    )

    # Import here to avoid circular imports if your ledger models reference reconciliation later
    from models.reconciliation import BankStatementLine  # noqa

    lines = session.query(BankStatementLine).filter_by(statement_id=stmt.id).all()

    for line in lines:
        if getattr(line, "matched", False):
            continue

        line_amt = _as_decimal(line.amount).quantize(Decimal("0.01"))

        for le in ledger_rows:
            le_amt = (_as_decimal(le.debit) - _as_decimal(le.credit)).quantize(Decimal("0.01"))
            if le_amt == line_amt:
                line.matched = True
                line.matched_journal_id = le.journal_id
                break

    session.commit()


def finalize_reconciliation(
    *,
    company_id,
    account_code: str,
    period: str,
) -> ReconciliationStatus:
    """
    Finalize reconciliation:
    - Period must exist and be CLOSED (not locked)
    - Bank statement must exist for account+period
    - Ledger balance must equal statement ending balance
    - Writes/updates reconciliation_status row
    """
    session: Session = db.session

    ap = (
        session.query(AccountingPeriod)
        .filter_by(company_id=company_id, period=period)
        .one_or_none()
    )
    if not ap:
        raise ReconciliationError("Accounting period not found")

    if getattr(ap, "status", None) != "closed":
        raise ReconciliationError("Period must be closed before reconciliation")

    stmt = (
        session.query(BankStatement)
        .filter_by(company_id=company_id, account_code=account_code, period=period)
        .one_or_none()
    )
    if not stmt:
        raise ReconciliationError("Bank statement not imported")

    ledger_balance = compute_ledger_balance(company_id=company_id, account_code=account_code, period=period)
    statement_balance = _as_decimal(stmt.ending_balance).quantize(Decimal("0.01"))

    if ledger_balance != statement_balance:
        raise ReconciliationError("Ledger balance does not match statement")

    rec = (
        session.query(ReconciliationStatus)
        .filter_by(company_id=company_id, account_code=account_code, period=period)
        .one_or_none()
    )

    if not rec:
        rec = ReconciliationStatus(
            company_id=company_id,
            account_code=account_code,
            period=period,
            ledger_balance=ledger_balance,
            statement_balance=statement_balance,
            is_reconciled=True,
            reconciled_at=datetime.utcnow(),
        )
        session.add(rec)
    else:
        rec.ledger_balance = ledger_balance
        rec.statement_balance = statement_balance
        rec.is_reconciled = True
        rec.reconciled_at = datetime.utcnow()

    session.commit()
    return rec

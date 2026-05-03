# services/reconciliation.py
# FULL FILE — reconciliation engine (ledger ↔ statement) — ROOT IMPORTS (Render-safe)

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db import db
from models.accounting_periods import AccountingPeriod
from models.ledger import Journal, LedgerEntry
from models.reconciliation import BankStatement, BankStatementLine, ReconciliationStatus


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
    period_code: str,  # YYYY-MM
) -> Decimal:
    """
    Ledger balance for an account up to and including a period (YYYY-MM).
    Period is derived from Journal.accounting_period (NOT a LedgerEntry.period field).
    """
    session: Session = db.session

    debit_sum = func.coalesce(func.sum(LedgerEntry.debit), 0)
    credit_sum = func.coalesce(func.sum(LedgerEntry.credit), 0)

    stmt = (
        select(debit_sum.label("debits"), credit_sum.label("credits"))
        .select_from(LedgerEntry)
        .join(Journal, Journal.id == LedgerEntry.journal_id)
        .where(
            LedgerEntry.company_id == company_id,
            LedgerEntry.account_code == account_code,
            Journal.company_id == company_id,
            Journal.accounting_period <= period_code,
        )
    )
    row = session.execute(stmt).one()

    bal = _as_decimal(row.debits) - _as_decimal(row.credits)
    return bal.quantize(Decimal("0.01"))


def match_statement_lines(*, statement_id) -> None:
    """
    Auto-match statement lines to ledger entries by exact net amount within same period/account.
    Stores matched_journal_id when found.

    Matching rule (v1):
      statement_line.amount == (ledger_entry.debit - ledger_entry.credit)
      within same company + account_code + period_code (via Journal.accounting_period)
    """
    session: Session = db.session

    stmt_bs = select(BankStatement).where(BankStatement.id == statement_id)
    stmt = session.execute(stmt_bs).scalar_one_or_none()
    if not stmt:
        raise ReconciliationError("Statement not found")

    stmt_le = (
        select(LedgerEntry)
        .join(Journal, Journal.id == LedgerEntry.journal_id)
        .where(
            LedgerEntry.company_id == stmt.company_id,
            LedgerEntry.account_code == stmt.account_code,
            Journal.company_id == stmt.company_id,
            Journal.accounting_period == stmt.period_code,
        )
    )
    ledger_rows = list(session.execute(stmt_le).scalars().all())

    lines = list(
        session.execute(
            select(BankStatementLine).where(BankStatementLine.statement_id == stmt.id)
        ).scalars().all()
    )

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
    period_code: str,  # YYYY-MM
) -> ReconciliationStatus:
    """
    Finalize reconciliation:
    - Accounting period must exist and be CLOSED (and not hard-locked)
    - Bank statement must exist for company+account+period_code
    - Ledger balance must equal statement ending balance
    - Writes/updates reconciliation_status row
    """
    session: Session = db.session

    ap = (
        session.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.company_id == company_id,
                AccountingPeriod.period_code == period_code,
            )
        ).scalar_one_or_none()
    )
    if not ap:
        raise ReconciliationError("Accounting period not found")

    if not ap.is_closed:
        raise ReconciliationError("Period must be closed before reconciliation")

    if ap.is_hard_locked:
        raise ReconciliationError("Period is hard locked")

    stmt = (
        session.execute(
            select(BankStatement).where(
                BankStatement.company_id == company_id,
                BankStatement.account_code == account_code,
                BankStatement.period_code == period_code,
            )
        ).scalar_one_or_none()
    )
    if not stmt:
        raise ReconciliationError("Bank statement not imported")

    ledger_balance = compute_ledger_balance(
        company_id=company_id,
        account_code=account_code,
        period_code=period_code,
    )
    statement_balance = _as_decimal(stmt.ending_balance).quantize(Decimal("0.01"))

    if ledger_balance != statement_balance:
        raise ReconciliationError("Ledger balance does not match statement")

    rec = (
        session.execute(
            select(ReconciliationStatus).where(
                ReconciliationStatus.company_id == company_id,
                ReconciliationStatus.account_code == account_code,
                ReconciliationStatus.period_code == period_code,
            )
        ).scalar_one_or_none()
    )

    if not rec:
        rec = ReconciliationStatus(
            company_id=company_id,
            account_code=account_code,
            period_code=period_code,
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

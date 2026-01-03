# freightpay/services/reporting.py
# REPORTING ENGINE — ledger-based source of truth (Trial Balance + P&L + Balance Sheet)

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import and_, func, case

from freightpay.models.ledger import LedgerEntry
from freightpay.models.chart_of_accounts import Account


@dataclass(frozen=True)
class ReportLine:
    account_code: str
    name: str
    account_type: str
    debit: Decimal
    credit: Decimal
    net: Decimal  # debit - credit for debit-normal accounts; credit - debit for credit-normal accounts


def _as_decimal(v) -> Decimal:
    if v is None:
        return Decimal("0.00")
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _period_filter(
    *,
    period_from: str,
    period_to: str,
):
    # period_code format YYYY-MM
    return and_(
        LedgerEntry.journal.has(),  # no-op safety; journal exists by FK
        LedgerEntry.journal_id.isnot(None),
        # NOTE: accounting period is stored on Journal; LedgerEntry itself doesn't store it in our model.
        # We join through Journal via relationship in the query below where needed.
    )


def trial_balance(
    db: Session,
    *,
    company_id,
    period_from: str,
    period_to: str,
) -> Dict:
    """
    Returns ledger-based Trial Balance for a period range (inclusive).
    Source of truth: ledger_entries joined to journals (period) and accounts (names/types).
    """

    # Join Accounts to ledger by account_code (stable key).
    # Join Journal to filter by accounting_period.
    from freightpay.models.ledger import Journal  # local import to avoid circulars

    rows = (
        db.query(
            Account.account_code.label("account_code"),
            Account.name.label("name"),
            Account.account_type.label("account_type"),
            Account.normal_balance.label("normal_balance"),
            func.coalesce(func.sum(LedgerEntry.debit), 0).label("debit"),
            func.coalesce(func.sum(LedgerEntry.credit), 0).label("credit"),
        )
        .join(
            LedgerEntry,
            and_(
                LedgerEntry.company_id == Account.company_id,
                LedgerEntry.account_code == Account.account_code,
            ),
        )
        .join(
            Journal,
            and_(
                Journal.id == LedgerEntry.journal_id,
                Journal.company_id == company_id,
            ),
        )
        .filter(
            Account.company_id == company_id,
            LedgerEntry.company_id == company_id,
            Journal.accounting_period >= period_from,
            Journal.accounting_period <= period_to,
            Account.is_active.is_(True),
        )
        .group_by(
            Account.account_code,
            Account.name,
            Account.account_type,
            Account.normal_balance,
        )
        .order_by(Account.account_code.asc())
        .all()
    )

    lines: List[ReportLine] = []
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")

    for r in rows:
        debit = _as_decimal(r.debit)
        credit = _as_decimal(r.credit)

        # Net presentation aligned to normal balance
        if r.normal_balance == "debit":
            net = debit - credit
        else:
            net = credit - debit

        total_debit += debit
        total_credit += credit

        lines.append(
            ReportLine(
                account_code=r.account_code,
                name=r.name,
                account_type=r.account_type,
                debit=debit,
                credit=credit,
                net=net,
            )
        )

    return {
        "company_id": str(company_id),
        "period_from": period_from,
        "period_to": period_to,
        "totals": {
            "debit": str(total_debit),
            "credit": str(total_credit),
            "is_balanced": total_debit == total_credit,
        },
        "lines": [
            {
                "account_code": l.account_code,
                "name": l.name,
                "account_type": l.account_type,
                "debit": str(l.debit),
                "credit": str(l.credit),
                "net": str(l.net),
            }
            for l in lines
        ],
    }


def profit_and_loss(
    db: Session,
    *,
    company_id,
    period_from: str,
    period_to: str,
) -> Dict:
    """
    Ledger-based Profit & Loss (Income Statement) for period range (inclusive).
    Includes only Revenue and Expense accounts.
    """
    tb = trial_balance(db, company_id=company_id, period_from=period_from, period_to=period_to)

    revenue = Decima

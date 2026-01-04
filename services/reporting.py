# services/reporting.py
# REPORTING ENGINE — ledger-based source of truth
# Trial Balance + P&L + Balance Sheet + Cash Flow
#
# RESTORED to original structure/intent
# Root-based imports only (freightpay removed)
# Line structure, comments, staging preserved
# Explicit TODO blocks added for reconciliation + cash classification (requested)

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Any

from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from models.ledger import LedgerEntry
from models.chart_of_accounts import Account


# ======================================================
# Data structures
# ======================================================

@dataclass(frozen=True)
class ReportLine:
    account_code: str
    name: str
    account_type: str
    debit: Decimal
    credit: Decimal
    net: Decimal  # debit - credit for debit-normal; credit - debit for credit-normal


# ======================================================
# Helpers
# ======================================================

def _as_decimal(v) -> Decimal:
    if v is None:
        return Decimal("0.00")
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _q2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"))


def _present_amount(account_type: str, normal_balance: str, net: Decimal) -> Decimal:
    """
    Present as positive amounts for typical financial statement readability.

    Design intent:
    - debit-normal accounts: net already positive when increased
    - credit-normal accounts: net is credit - debit (positive when increased)

    NOTE:
    account_type is intentionally unused today but retained to support:
    - contra accounts
    - presentation overrides
    - future GAAP / IFRS formatting rules
    """
    _ = account_type  # reserved for future refinements / validations

    if normal_balance == "debit":
        return _q2(net)

    return _q2(net)


# ======================================================
# Trial Balance
# ======================================================

def trial_balance(
    db: Session,
    *,
    company_id,
    period_from: str,
    period_to: str,
) -> Dict[str, Any]:
    """
    Ledger-based Trial Balance for a period range (inclusive).

    Source of truth:
    - LedgerEntry (debits/credits)
    - Journal (accounting_period)
    - Chart of Accounts (names, types, normal balance)
    """

    # Local import to avoid circular dependencies
    from models.ledger import Journal

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
        debit = _q2(_as_decimal(r.debit))
        credit = _q2(_as_decimal(r.credit))

        # Net aligned to normal balance
        if r.normal_balance == "debit":
            net = _q2(debit - credit)
        else:
            net = _q2(credit - debit)

        total_debit += debit
        total_credit += credit

        lines.append(
            ReportLine(
                account_code=str(r.account_code),
                name=str(r.name),
                account_type=str(r.account_type),
                debit=debit,
                credit=credit,
                net=net,
            )
        )

    total_debit = _q2(total_debit)
    total_credit = _q2(total_credit)

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


# ======================================================
# Profit & Loss
# ======================================================

def profit_and_loss(
    db: Session,
    *,
    company_id,
    period_from: str,
    period_to: str,
) -> Dict[str, Any]:
    """
    Ledger-based Profit & Loss (Income Statement).

    Includes:
    - Revenue accounts
    - Expense accounts

    Excludes:
    - Assets
    - Liabilities
    - Equity
    """

    tb = trial_balance(db, company_id=company_id, period_from=period_from, period_to=period_to)

    revenue_total = Decimal("0.00")
    expense_total = Decimal("0.00")

    revenue_lines: List[Dict[str, str]] = []
    expense_lines: List[Dict[str, str]] = []

    for l in tb["lines"]:
        account_type = l["account_type"]
        net = _as_decimal(l["net"])

        if account_type == "revenue":
            amt = _q2(net)
            revenue_total += amt
            revenue_lines.append(
                {
                    "account_code": l["account_code"],
                    "name": l["name"],
                    "amount": str(amt),
                }
            )

        if account_type == "expense":
            amt = _q2(net)
            expense_total += amt
            expense_lines.append(
                {
                    "account_code": l["account_code"],
                    "name": l["name"],
                    "amount": str(amt),
                }
            )

    revenue_total = _q2(revenue_total)
    expense_total = _q2(expense_total)
    net_income = _q2(revenue_total - expense_total)

    return {
        "company_id": str(company_id),
        "period_from": period_from,
        "period_to": period_to,
        "revenue": {"total": str(revenue_total), "lines": revenue_lines},
        "expenses": {"total": str(expense_total), "lines": expense_lines},
        "net_income": str(net_income),
    }


# ======================================================
# Balance Sheet
# ======================================================

def balance_sheet(
    db: Session,
    *,
    company_id,
    period_from: str,
    period_to: str,
) -> Dict[str, Any]:
    """
    Ledger-based Balance Sheet.

    Assets = Liabilities + Equity
    """

    tb = trial_balance(db, company_id=company_id, period_from=period_from, period_to=period_to)

    assets_total = Decimal("0.00")
    liabilities_total = Decimal("0.00")
    equity_total = Decimal("0.00")

    assets_lines: List[Dict[str, str]] = []
    liabilities_lines: List[Dict[str, str]] = []
    equity_lines: List[Dict[str, str]] = []

    # Lookup normal balance + names from chart
    codes = [l["account_code"] for l in tb["lines"]]
    account_rows = (
        db.query(Account.account_code, Account.normal_balance, Account.account_type, Account.name)
        .filter(Account.company_id == company_id, Account.account_code.in_(codes))
        .all()
    )
    acct_lookup = {str(r.account_code): r for r in account_rows}

    for l in tb["lines"]:
        code = l["account_code"]
        net = _as_decimal(l["net"])
        acct = acct_lookup.get(code)

        if not acct:
            continue

        amt = _present_amount(acct.account_type, acct.normal_balance, net)

        if acct.account_type == "asset":
            assets_total += amt
            assets_lines.append({"account_code": code, "name": acct.name, "amount": str(_q2(amt))})

        elif acct.account_type == "liability":
            liabilities_total += amt
            liabilities_lines.append({"account_code": code, "name": acct.name, "amount": str(_q2(amt))})

        elif acct.account_type == "equity":
            equity_total += amt
            equity_lines.append({"account_code": code, "name": acct.name, "amount": str(_q2(amt))})

    assets_total = _q2(assets_total)
    liabilities_total = _q2(liabilities_total)
    equity_total = _q2(equity_total)

    return {
        "company_id": str(company_id),
        "period_from": period_from,
        "period_to": period_to,
        "assets": {"total": str(assets_total), "lines": assets_lines},
        "liabilities": {"total": str(liabilities_total), "lines": liabilities_lines},
        "equity": {"total": str(equity_total), "lines": equity_lines},
        "is_balanced": assets_total == _q2(liabilities_total + equity_total),
    }


# ======================================================
# Cash Flow
# ======================================================

def cash_flow(
    db: Session,
    *,
    company_id,
    period_from: str,
    period_to: str,
) -> Dict[str, Any]:
    """
    MVP Cash Flow — indirect method (stub).

    TODO (Reconciliation Integration):
    - Replace net-income-only logic with:
        - operating cash adjustments
        - non-cash expenses (depreciation, amortization)
        - working capital changes (AR, AP, inventory)

    TODO (Bank Reconciliation Dependency):
    - Derive actual cash movement from reconciled bank transactions
    - Enforce period must be reconciled before final cash flow is “locked”
    """

    pnl = profit_and_loss(db, company_id=company_id, period_from=period_from, period_to=period_to)
    net_income = _q2(_as_decimal(pnl["net_income"]))

    return {
        "company_id": str(company_id),
        "period_from": period_from,
        "period_to": period_to,
        "method": "indirect_stub",
        "net_income": str(net_income),
        "operating_cash_flow": str(net_income),
        "investing_cash_flow": "0.00",
        "financing_cash_flow": "0.00",
        "net_change_in_cash": str(net_income),
    }


# ======================================================
# Combined Financials
# ======================================================

def financials(
    db: Session,
    *,
    company_id,
    period_from: str,
    period_to: str,
) -> Dict[str, Any]:
    """
    Convenience wrapper: Trial Balance + P&L + Balance Sheet + Cash Flow.

    TODO:
    - Add period-lock enforcement (no reporting on unclosed periods)
    - Snapshot reports for audit trail
    """

    tb = trial_balance(db, company_id=company_id, period_from=period_from, period_to=period_to)
    pnl = profit_and_loss(db, company_id=company_id, period_from=period_from, period_to=period_to)
    bs = balance_sheet(db, company_id=company_id, period_from=period_from, period_to=period_to)
    cf = cash_flow(db, company_id=company_id, period_from=period_from, period_to=period_to)

    return {
        "trial_balance": tb,
        "profit_and_loss": pnl,
        "balance_sheet": bs,
        "cash_flow": cf,
    }


# freightpay/services/settlement_posting.py
# Purpose: Post contractor/driver settlements into the General Ledger (double-entry) using post_journal()
# Status: FULL PRODUCTION HARDENED
# Date: 2026-02-14

from __future__ import annotations

import os
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from services.post_journal import post_journal


_Q2 = Decimal("0.01")


def _money(v: Any, *, field: str, allow_negative: bool = False) -> Decimal:
    if v is None or v == "":
        d = Decimal("0.00")
    else:
        try:
            d = Decimal(str(v).strip())
        except (InvalidOperation, ValueError):
            raise ValueError(f"INVALID_MONEY_VALUE:{field}")

    d = d.quantize(_Q2, rounding=ROUND_HALF_UP)
    if not allow_negative and d < 0:
        raise ValueError(f"NEGATIVE_MONEY_VALUE:{field}")
    return d


def _validate_period(period: str) -> str:
    p = (period or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}", p):
        raise ValueError("INVALID_ACCOUNTING_PERIOD")
    return p


def _acct(env_key: str, default_code: str) -> str:
    v = (os.getenv(env_key) or "").strip()
    return v if v else default_code


def post_settlement(
    db: Session,
    *,
    company_id,
    settlement_id,
    accounting_period: str,
    posted_by,
    totals: Dict[str, Any],
    deductions: Optional[Dict[str, Any]] = None,
    description: Optional[str] = None,
):
    """
    Contractor/driver settlement posting (accrual; cash posted separately when paid):

      DR 5400 Driver Pay / Contractor Expense           = gross_pay
      CR 2001 Settlements Payable (Net Pay)            = net_pay
      CR 1200 Fuel Advances (asset reduction)          = fuel_advance_recovery (optional)
      CR 2100 Driver Escrow (liability)                = escrow_withheld (optional)
      CR 2000 Accounts Payable (other deductions)      = other_deductions (optional)

    Balance rule:
      gross_pay MUST equal net_pay + total_deductions (within 1 cent)
    """
    if totals is None or not isinstance(totals, dict):
        raise ValueError("SETTLEMENT_TOTALS_REQUIRED")

    accounting_period = _validate_period(accounting_period)

    gross_pay = _money(totals.get("gross_pay"), field="gross_pay")
    net_pay = _money(totals.get("net_pay"), field="net_pay")

    d = deductions if isinstance(deductions, dict) else {}
    fuel_adv_recovery = _money(d.get("fuel_advances") or d.get("fuel_advance_recovery"), field="deductions.fuel_advances")
    escrow_withheld = _money(d.get("escrow") or d.get("escrow_withheld"), field="deductions.escrow")
    other_deductions = _money(d.get("other") or d.get("other_deductions"), field="deductions.other")

    total_deductions = (fuel_adv_recovery + escrow_withheld + other_deductions).quantize(_Q2, rounding=ROUND_HALF_UP)
    expected_gross = (net_pay + total_deductions).quantize(_Q2, rounding=ROUND_HALF_UP)

    # allow a 1-cent tolerance for upstream rounding
    if (gross_pay - expected_gross).copy_abs() > Decimal("0.01"):
        raise ValueError(
            f"UNBALANCED_SETTLEMENT: gross_pay({gross_pay}) != net_pay({net_pay}) + deductions({total_deductions})"
        )

    # Account codes (defaults align to your trucking COA template)
    ACCT_DRIVER_PAY_EXPENSE = _acct("ACCT_DRIVER_PAY_EXPENSE", "5400")
    ACCT_SETTLEMENTS_PAYABLE = _acct("ACCT_SETTLEMENTS_PAYABLE", "2001")
    ACCT_FUEL_ADVANCES = _acct("ACCT_FUEL_ADVANCES", "1200")
    ACCT_DRIVER_ESCROW = _acct("ACCT_DRIVER_ESCROW", "2100")
    ACCT_OTHER_DEDUCTIONS = _acct("ACCT_OTHER_DEDUCTIONS", "2000")

    entries = []

    if gross_pay > 0:
        entries.append({"account_code": ACCT_DRIVER_PAY_EXPENSE, "debit": gross_pay, "credit": Decimal("0.00")})

    if net_pay > 0:
        entries.append({"account_code": ACCT_SETTLEMENTS_PAYABLE, "debit": Decimal("0.00"), "credit": net_pay})

    if fuel_adv_recovery > 0:
        entries.append({"account_code": ACCT_FUEL_ADVANCES, "debit": Decimal("0.00"), "credit": fuel_adv_recovery})

    if escrow_withheld > 0:
        entries.append({"account_code": ACCT_DRIVER_ESCROW, "debit": Decimal("0.00"), "credit": escrow_withheld})

    if other_deductions > 0:
        entries.append({"account_code": ACCT_OTHER_DEDUCTIONS, "debit": Decimal("0.00"), "credit": other_deductions})

    if not entries:
        raise ValueError("NO_ENTRIES_TO_POST")

    desc = (description or "").strip() or f"Settlement {settlement_id}"

    return post_journal(
        db,
        company_id=company_id,
        source_type="settlement",
        source_id=settlement_id,
        accounting_period=accounting_period,
        description=desc,
        posted_by=posted_by,
        entries=entries,
    )

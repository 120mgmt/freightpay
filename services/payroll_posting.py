# freightpay/services/payroll_posting.py
# Purpose: Post payroll runs into the General Ledger (double-entry) using post_journal()
# Status: FULL PRODUCTION HARDENED
# Date: 2026-02-14

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from services.post_journal import post_journal


_Q2 = Decimal("0.01")


def _money(v: Any, *, field: str, allow_negative: bool = False) -> Decimal:
    """
    Crash-proof Decimal parsing with 2dp quantization.
    Rejects negatives by default.
    """
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


def post_payroll_run(
    db: Session,
    *,
    company_id,
    payroll_run_id,
    accounting_period: str,
    posted_by,
    totals: Dict[str, Any],
    description: Optional[str] = None,
):
    """
    Posts payroll run as:
      DR 5000 Wages Expense                         = gross_wages
      DR 5100 Payroll Tax Expense                   = employer_fica + futa + suta
      CR 2110 Federal Withholding Payable           = employee_withholding_federal
      CR 2120 State Withholding Payable             = employee_withholding_state
      CR 2130 Employee FICA Payable                 = employee_fica
      CR 2140 Employer FICA Payable                 = employer_fica
      CR 2150 FUTA Payable                          = futa
      CR 2160 SUTA Payable                          = suta
      CR 2100 Payroll Payable (Net Pay)             = net_pay

    NOTE:
      - This posts liabilities/expenses only.
      - Cash is posted when the payout is executed (separate payout posting service).
    """
    if totals is None or not isinstance(totals, dict):
        raise ValueError("PAYROLL_TOTALS_REQUIRED")

    accounting_period = _validate_period(accounting_period)

    gross_wages = _money(totals.get("gross_wages"), field="gross_wages")

    fed_wh = _money(totals.get("employee_withholding_federal"), field="employee_withholding_federal")
    st_wh = _money(totals.get("employee_withholding_state"), field="employee_withholding_state")
    ee_fica = _money(totals.get("employee_fica"), field="employee_fica")

    er_fica = _money(totals.get("employer_fica"), field="employer_fica")
    futa = _money(totals.get("futa"), field="futa")
    suta = _money(totals.get("suta"), field="suta")

    net_pay = _money(totals.get("net_pay"), field="net_pay")

    entries = []

    # Expenses
    if gross_wages > 0:
        entries.append({"account_code": "5000", "debit": gross_wages, "credit": Decimal("0.00")})

    employer_taxes = (er_fica + futa + suta).quantize(_Q2, rounding=ROUND_HALF_UP)
    if employer_taxes > 0:
        entries.append({"account_code": "5100", "debit": employer_taxes, "credit": Decimal("0.00")})

    # Liabilities
    if fed_wh > 0:
        entries.append({"account_code": "2110", "debit": Decimal("0.00"), "credit": fed_wh})
    if st_wh > 0:
        entries.append({"account_code": "2120", "debit": Decimal("0.00"), "credit": st_wh})
    if ee_fica > 0:
        entries.append({"account_code": "2130", "debit": Decimal("0.00"), "credit": ee_fica})

    if er_fica > 0:
        entries.append({"account_code": "2140", "debit": Decimal("0.00"), "credit": er_fica})
    if futa > 0:
        entries.append({"account_code": "2150", "debit": Decimal("0.00"), "credit": futa})
    if suta > 0:
        entries.append({"account_code": "2160", "debit": Decimal("0.00"), "credit": suta})

    if net_pay > 0:
        entries.append({"account_code": "2100", "debit": Decimal("0.00"), "credit": net_pay})

    if not entries:
        raise ValueError("NO_ENTRIES_TO_POST")

    desc = (description or "").strip() or f"Payroll run {payroll_run_id}"

    return post_journal(
        db,
        company_id=company_id,
        source_type="payroll",
        source_id=payroll_run_id,
        accounting_period=accounting_period,
        description=desc,
        posted_by=posted_by,
        entries=entries,
    )

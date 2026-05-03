# File: services/payroll_journalization.py
# Purpose: Enterprise-hardened payroll and 1099 contractor journalization
# Status: Go-live ready

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from services.ledger_posting_guard import post_journal


_Q2 = Decimal("0.01")


def _money(value: Any, *, field: str, allow_negative: bool = False) -> Decimal:
    if value is None or value == "":
        amount = Decimal("0.00")
    else:
        try:
            amount = Decimal(str(value).strip())
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError(f"INVALID_MONEY_VALUE:{field}") from exc

    amount = amount.quantize(_Q2, rounding=ROUND_HALF_UP)

    if not allow_negative and amount < 0:
        raise ValueError(f"NEGATIVE_MONEY_VALUE:{field}")

    return amount


def _validate_period(accounting_period: str) -> str:
    period = (accounting_period or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}", period):
        raise ValueError("INVALID_ACCOUNTING_PERIOD")
    return period


def _validate_required_id(value: Any, field: str) -> str:
    text_value = str(value).strip() if value is not None else ""
    if not text_value:
        raise ValueError(f"MISSING_{field.upper()}")
    return text_value


def _build_description(prefix: str, source_id: Any, override: Optional[str]) -> str:
    if override and str(override).strip():
        return str(override).strip()
    return f"{prefix} {source_id}"


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
    W-2 payroll journalization.

    DR 5000 Wages Expense
    DR 5100 Payroll Tax Expense
    CR 2110 Federal Withholding Payable
    CR 2120 State Withholding Payable
    CR 2130 Employee FICA Payable
    CR 2140 Employer FICA Payable
    CR 2150 FUTA Payable
    CR 2160 SUTA Payable
    CR 2100 Payroll Payable (Net Pay)

    Cash is not posted here. Cash is posted separately at payout time.
    """

    if totals is None or not isinstance(totals, dict):
        raise ValueError("PAYROLL_TOTALS_REQUIRED")

    accounting_period = _validate_period(accounting_period)
    payroll_run_id = _validate_required_id(payroll_run_id, "payroll_run_id")

    gross_wages = _money(totals.get("gross_wages"), field="gross_wages")
    fed_wh = _money(
        totals.get("employee_withholding_federal"),
        field="employee_withholding_federal",
    )
    st_wh = _money(
        totals.get("employee_withholding_state"),
        field="employee_withholding_state",
    )
    ee_fica = _money(totals.get("employee_fica"), field="employee_fica")
    er_fica = _money(totals.get("employer_fica"), field="employer_fica")
    futa = _money(totals.get("futa"), field="futa")
    suta = _money(totals.get("suta"), field="suta")
    net_pay = _money(totals.get("net_pay"), field="net_pay")

    expected_net = (gross_wages - fed_wh - st_wh - ee_fica).quantize(
        _Q2,
        rounding=ROUND_HALF_UP,
    )
    if expected_net != net_pay:
        raise ValueError("NET_PAY_DOES_NOT_RECONCILE")

    entries = []

    if gross_wages > 0:
        entries.append(
            {
                "account_code": "5000",
                "debit": gross_wages,
                "credit": Decimal("0.00"),
            }
        )

    employer_taxes = (er_fica + futa + suta).quantize(_Q2, rounding=ROUND_HALF_UP)
    if employer_taxes > 0:
        entries.append(
            {
                "account_code": "5100",
                "debit": employer_taxes,
                "credit": Decimal("0.00"),
            }
        )

    if fed_wh > 0:
        entries.append(
            {
                "account_code": "2110",
                "debit": Decimal("0.00"),
                "credit": fed_wh,
            }
        )
    if st_wh > 0:
        entries.append(
            {
                "account_code": "2120",
                "debit": Decimal("0.00"),
                "credit": st_wh,
            }
        )
    if ee_fica > 0:
        entries.append(
            {
                "account_code": "2130",
                "debit": Decimal("0.00"),
                "credit": ee_fica,
            }
        )
    if er_fica > 0:
        entries.append(
            {
                "account_code": "2140",
                "debit": Decimal("0.00"),
                "credit": er_fica,
            }
        )
    if futa > 0:
        entries.append(
            {
                "account_code": "2150",
                "debit": Decimal("0.00"),
                "credit": futa,
            }
        )
    if suta > 0:
        entries.append(
            {
                "account_code": "2160",
                "debit": Decimal("0.00"),
                "credit": suta,
            }
        )
    if net_pay > 0:
        entries.append(
            {
                "account_code": "2100",
                "debit": Decimal("0.00"),
                "credit": net_pay,
            }
        )

    if not entries:
        raise ValueError("NO_ENTRIES_TO_POST")

    return post_journal(
        db,
        company_id=company_id,
        source_type="payroll",
        source_id=payroll_run_id,
        accounting_period=accounting_period,
        description=_build_description("Payroll run", payroll_run_id, description),
        posted_by=posted_by,
        entries=entries,
    )


def post_contractor_run(
    db: Session,
    *,
    company_id,
    contractor_run_id,
    accounting_period: str,
    posted_by,
    totals: Dict[str, Any],
    description: Optional[str] = None,
):
    """
    1099 contractor journalization.

    DR 5200 Contractor Expense
    CR 2200 Contractor Payable

    Cash is not posted here. Cash is posted separately when payout occurs.
    """

    if totals is None or not isinstance(totals, dict):
        raise ValueError("CONTRACTOR_TOTALS_REQUIRED")

    accounting_period = _validate_period(accounting_period)
    contractor_run_id = _validate_required_id(contractor_run_id, "contractor_run_id")

    gross_contract_pay = _money(
        totals.get("gross_contract_pay"),
        field="gross_contract_pay",
    )
    reimbursements = _money(
        totals.get("reimbursements"),
        field="reimbursements",
    )
    deductions = _money(
        totals.get("deductions"),
        field="deductions",
    )
    net_pay = _money(totals.get("net_pay"), field="net_pay")

    expected_net = (gross_contract_pay + reimbursements - deductions).quantize(
        _Q2,
        rounding=ROUND_HALF_UP,
    )
    if expected_net != net_pay:
        raise ValueError("CONTRACTOR_NET_DOES_NOT_RECONCILE")

    total_expense = (gross_contract_pay + reimbursements).quantize(
        _Q2,
        rounding=ROUND_HALF_UP,
    )

    entries = []

    if total_expense > 0:
        entries.append(
            {
                "account_code": "5200",
                "debit": total_expense,
                "credit": Decimal("0.00"),
            }
        )

    if deductions > 0:
        entries.append(
            {
                "account_code": "2210",
                "debit": Decimal("0.00"),
                "credit": deductions,
            }
        )

    if net_pay > 0:
        entries.append(
            {
                "account_code": "2200",
                "debit": Decimal("0.00"),
                "credit": net_pay,
            }
        )

    if not entries:
        raise ValueError("NO_ENTRIES_TO_POST")

    return post_journal(
        db,
        company_id=company_id,
        source_type="contractor",
        source_id=contractor_run_id,
        accounting_period=accounting_period,
        description=_build_description(
            "Contractor run",
            contractor_run_id,
            description,
        ),
        posted_by=posted_by,
        entries=entries,
    )

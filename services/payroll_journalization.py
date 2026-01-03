# freightpay/services/payroll_journalization.py
# PAYROLL → LEDGER JOURNALIZATION (posts expenses + liabilities only; payout clears cash separately)

from decimal import Decimal
from sqlalchemy.orm import Session

from freightpay.services.ledger_posting_guard import post_journal


def post_payroll_run(
    db: Session,
    *,
    company_id,
    payroll_run_id,
    accounting_period: str,
    posted_by,
    payroll_totals: dict,
):
    """
    payroll_totals expected keys:
    - gross_wages
    - employee_withholding_federal
    - employee_withholding_state
    - employee_fica
    - employer_fica
    - futa
    - suta
    - net_pay

    IMPORTANT:
    - This function does NOT post Cash.
    - Cash is posted when the payout occurs (see payroll_payouts.post_payroll_payout).
    """

    gross_wages = Decimal(payroll_totals["gross_wages"])

    fed_wh = Decimal(payroll_totals["employee_withholding_federal"])
    st_wh = Decimal(payroll_totals["employee_withholding_state"])
    ee_fica = Decimal(payroll_totals["employee_fica"])

    er_fica = Decimal(payroll_totals["employer_fica"])
    futa = Decimal(payroll_totals["futa"])
    suta = Decimal(payroll_totals["suta"])

    net_pay = Decimal(payroll_totals["net_pay"])

    entries = []

    # Expenses
    if gross_wages > 0:
        entries.append({"account_code": "5000", "debit": gross_wages, "credit": Decimal("0.00")})  # Wages Expense

    employer_taxes = er_fica + futa + suta
    if employer_taxes > 0:
        entries.append({"account_code": "5100", "debit": employer_taxes, "credit": Decimal("0.00")})  # Payroll Tax Exp

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
        entries.append({"account_code": "2100", "debit": Decimal("0.00"), "credit": net_pay})  # Payroll Payable

    return post_journal(
        db,
        company_id=company_id,
        source_type="payroll",
        source_id=payroll_run_id,
        accounting_period=accounting_period,
        description=f"Payroll run {payroll_run_id}",
        posted_by=posted_by,
        entries=entries,
    )

  

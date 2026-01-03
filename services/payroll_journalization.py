# freightpay/services/payroll_journalization.py
# PAYROLL → LEDGER JOURNALIZATION (native, compliance-safe)

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
    """

    entries = []

    # Gross wages expense
    entries.append(
        {
            "account_code": "5000",  # Wages Expense
            "debit": Decimal(payroll_totals["gross_wages"]),
            "credit": Decimal("0.00"),
        }
    )

    # Employee withholdings (liabilities)
    entries.extend(
        [
            {
                "account_code": "2110",  # Federal Withholding Payable
                "debit": Decimal("0.00"),
                "credit": Decimal(payroll_totals["employee_withholding_federal"]),
            },
            {
                "account_code": "2120",  # State Withholding Payable
                "debit": Decimal("0.00"),
                "credit": Decimal(payroll_totals["employee_withholding_state"]),
            },
            {
                "account_code": "2130",  # FICA Payable (Employee)
                "debit": Decimal("0.00"),
                "credit": Decimal(payroll_totals["employee_fica"]),
            },
        ]
    )

    # Employer payroll taxes expense + liability
    employer_taxes = (
        Decimal(payroll_totals["employer_fica"])
        + Decimal(payroll_totals["futa"])
        + Decimal(payroll_totals["suta"])
    )

    entries.append(
        {
            "account_code": "5100",  # Payroll Tax Expense (Employer)
            "debit": employer_taxes,
            "credit": Decimal("0.00"),
        }
    )

    entries.extend(
        [
            {
                "account_code": "2140",  # FICA Payable (Employer)
                "debit": Decimal("0.00"),
                "credit": Decimal(payroll_totals["employer_fica"]),
            },
            {
                "account_code": "2150",  # FUTA Payable
                "debit": Decimal("0.00"),
                "credit": Decimal(payroll_totals["futa"]),
            },
            {
                "account_code": "2160",  # SUTA Payable
                "debit": Decimal("0.00"),
                "credit": Decimal(payroll_totals["suta"]),
            },
        ]
    )

    # Net pay liability
    entries.append(
        {
            "account_code": "2100",  # Payroll Payable
            "debit": Decimal("0.00"),
            "credit": Decimal(payroll_totals["net_pay"]),
        }
    )

    # Cash clearing (when payroll is funded)
    entries.append(
        {
            "account_code": "1000",  # Cash
            "debit": Decimal("0.00"),
            "credit": Decimal(payroll_totals["net_pay"]),
        }
    )

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

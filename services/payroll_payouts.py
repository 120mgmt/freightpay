# freightpay/services/payroll_payouts.py
# PAYROLL PAYOUT POSTING + LIABILITY CLEARING (net pay payable -> cash)

from decimal import Decimal
from sqlalchemy.orm import Session

from freightpay.services.ledger_posting_guard import post_journal


def post_payroll_payout(
    db: Session,
    *,
    company_id,
    payout_id,
    payroll_run_id,
    accounting_period: str,
    posted_by,
    amount: str,
    cash_account_code: str = "1000",
):
    """
    Clears Payroll Payable when money is paid out.

    DR Payroll Payable (2100)
    CR Cash (1000)

    amount: string/decimal compatible (e.g. "12450.67")
    """

    amt = Decimal(amount)
    if amt <= 0:
        raise ValueError("Payout amount must be positive")

    entries = [
        {
            "account_code": "2100",  # Payroll Payable
            "debit": amt,
            "credit": Decimal("0.00"),
        },
        {
            "account_code": cash_account_code,  # Cash
            "debit": Decimal("0.00"),
            "credit": amt,
        },
    ]

    return post_journal(
        db,
        company_id=company_id,
        source_type="payment",
        source_id=payout_id,
        accounting_period=accounting_period,
        description=f"Payroll payout for run {payroll_run_id}",
        posted_by=posted_by,
        entries=entries,
    )

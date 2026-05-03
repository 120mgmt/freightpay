# freightpay/services/tax_liability_payments.py
# TAX PAYMENT POSTING + LIABILITY CLEARING (ledger-safe)

from decimal import Decimal
from sqlalchemy.orm import Session

from services.ledger_posting_guard import post_journal


def post_tax_payment(
    db: Session,
    *,
    company_id,
    payment_id,
    accounting_period: str,
    posted_by,
    authority: str,
    amounts: dict,
    cash_account_code: str = "1000",
):
    """
    authority: "federal" | "state" | "local"

    amounts expected keys (include only those you are paying):
      - federal_withholding
      - state_withholding
      - fica_employee
      - fica_employer
      - futa
      - suta

    Posts: Debit liability accounts, Credit cash.
    """

    liability_map = {
        "federal_withholding": "2110",  # Federal Withholding Payable
        "state_withholding": "2120",    # State Withholding Payable
        "fica_employee": "2130",        # FICA Payable (Employee)
        "fica_employer": "2140",        # FICA Payable (Employer)
        "futa": "2150",                 # FUTA Payable
        "suta": "2160",                 # SUTA Payable
    }

    entries = []
    total_cash = Decimal("0.00")

    for k, v in (amounts or {}).items():
        if k not in liability_map:
            continue
        amt = Decimal(v)
        if amt <= 0:
            continue

        total_cash += amt
        entries.append(
            {
                "account_code": liability_map[k],
                "debit": amt,              # reduce liability
                "credit": Decimal("0.00"),
            }
        )

    if total_cash <= 0:
        raise ValueError("No positive tax amounts provided")

    # Credit cash for total payment
    entries.append(
        {
            "account_code": cash_account_code,
            "debit": Decimal("0.00"),
            "credit": total_cash,
        }
    )

    return post_journal(
        db,
        company_id=company_id,
        source_type="tax",
        source_id=payment_id,
        accounting_period=accounting_period,
        description=f"{authority.capitalize()} payroll tax payment {payment_id}",
        posted_by=posted_by,
        entries=entries,
    )

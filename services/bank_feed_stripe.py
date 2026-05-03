# freightpay/services/bank_feed_stripe.py
# STRIPE FINANCIAL CONNECTIONS → BANK TRANSACTIONS INGESTION (production-ready)

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

import stripe
from sqlalchemy.orm import Session

from models.ledger import Journal, LedgerEntry
from services.ledger_posting_guard import post_journal


class BankFeedError(Exception):
    pass


def ingest_stripe_bank_transactions(
    db: Session,
    *,
    company_id,
    account_code: str,           # e.g. 1000 CASH
    accounting_period: str,      # YYYY-MM
    posted_by,
    stripe_account_id: str,      # Financial Connections account
    stripe_secret_key: str,
):
    """
    Pulls transactions from Stripe Financial Connections and posts them to the ledger.

    NOTE:
    - Uses Stripe Financial Connections Transactions API
    - Assumes Financial Connections account already linked
    - Posts each transaction as its own journal (immutable)
    """

    stripe.api_key = stripe_secret_key

    try:
        txns = stripe.financial_connections.Transaction.list(
            account=stripe_account_id,
            limit=100,
        )
    except Exception as e:
        raise BankFeedError(f"Stripe fetch failed: {e}")

    for txn in txns.auto_paging_iter():
        amount = Decimal(str(abs(txn.amount))) / Decimal("100")

        # Stripe: credits are negative, debits positive (bank perspective)
        if txn.amount < 0:
            debit = amount
            credit = Decimal("0.00")
        else:
            debit = Decimal("0.00")
            credit = amount

        entries = [
            {
                "account_code": account_code,
                "debit": debit,
                "credit": credit,
            }
        ]

        # Offset goes to clearing until reconciled
        entries.append(
            {
                "account_code": "1099",  # BANK CLEARING
                "debit": credit,
                "credit": debit,
            }
        )

        post_journal(
            db,
            company_id=company_id,
            source_type="bank_feed",
            source_id=txn.id,
            accounting_period=accounting_period,
            description=f"Bank txn: {txn.description or txn.id}",
            posted_by=posted_by,
            entries=entries,
        )

    return {"imported": True}

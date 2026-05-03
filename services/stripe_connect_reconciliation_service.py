# File: services/stripe_connect_reconciliation_service.py
# Purpose: Enterprise Stripe Connect reconciliation + retry engine
# Status: ENTERPRISE HARDNESS (retry-safe, ledger-aware, failure recovery)
# Date: 2026-02-25

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

import stripe
from sqlalchemy import select

from db import db
from billing.stripe_client import init_stripe
from models.driver_settlement import DriverSettlement


class StripeConnectReconciliationService:
    """
    Enterprise responsibilities:

    - Detect settlements marked paid but not confirmed
    - Detect failed transfers and revert safely
    - Re-query Stripe for authoritative status
    - Repair state drift
    - Safe for scheduled background execution
    """

    @staticmethod
    def _get_unconfirmed_settlements(hours: int = 24) -> List[DriverSettlement]:
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        return db.session.execute(
            select(DriverSettlement)
            .where(
                DriverSettlement.paid == True,
                DriverSettlement.payout_confirmed == False,
                DriverSettlement.created_at >= cutoff,
            )
        ).scalars().all()

    @classmethod
    def reconcile_recent_transfers(cls, lookback_hours: int = 24) -> int:
        """
        Reconcile payout state against Stripe authoritative transfer status.
        Safe to run via cron every 5–10 minutes.
        """

        init_stripe()

        settlements = cls._get_unconfirmed_settlements(lookback_hours)

        reconciled_count = 0

        for settlement in settlements:

            if not settlement.payout_reference:
                continue

            try:
                transfer = stripe.Transfer.retrieve(
                    settlement.payout_reference
                )
            except Exception:
                continue  # Stripe temporary issue — retry next cycle

            status = transfer.get("status")

            with db.session.begin():

                locked_settlement = db.session.execute(
                    select(DriverSettlement)
                    .where(DriverSettlement.id == settlement.id)
                    .with_for_update()
                ).scalar_one()

                if status == "paid":
                    locked_settlement.payout_confirmed = True
                    reconciled_count += 1

                elif status in {"failed", "canceled"}:
                    locked_settlement.paid = False
                    locked_settlement.payout_confirmed = False
                    reconciled_count += 1

                # pending stays untouched

        return reconciled_count

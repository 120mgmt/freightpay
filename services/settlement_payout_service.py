# File: services/settlement_payout_service.py
# Purpose: Hardened Settlement → Stripe Connect payout bridge
# Status: Production-ready (idempotent, locked, journal-integrated)
# Date: 2026-02-25

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from db import db
from billing.stripe_connect import StripeConnectService, StripeConnectedAccount
from models.driver_settlement import DriverSettlement
from models.general_ledger import GeneralLedgerService


class SettlementPayoutService:

    @staticmethod
    def _d(v):
        return Decimal(str(v or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @classmethod
    def execute(
        cls,
        *,
        settlement_id,
        executed_by_user_id: int,
        cash_account_id: int,
        contractor_expense_account_id: int,
    ):

        with db.session.begin():

            settlement = db.session.execute(
                select(DriverSettlement)
                .where(DriverSettlement.id == settlement_id)
                .with_for_update()
            ).scalar_one()

            if not settlement.locked:
                raise Exception("Settlement must be locked before payout.")

            if settlement.net_amount <= 0:
                raise Exception("Settlement net amount must be positive.")

            if getattr(settlement, "paid", False):
                raise Exception("Settlement already paid.")

            connected = db.session.execute(
                select(StripeConnectedAccount)
                .where(
                    StripeConnectedAccount.company_id == settlement.company_id,
                    StripeConnectedAccount.contractor_id == settlement.driver_id,
                )
            ).scalar_one()

            if not StripeConnectService.check_account_status(
                stripe_account_id=connected.stripe_account_id
            ):
                raise Exception("Stripe account not fully onboarded.")

            payout = StripeConnectService.send_payout(
                stripe_account_id=connected.stripe_account_id,
                amount=cls._d(settlement.net_amount),
                description=f"Settlement {settlement.period_label}",
            )

            GeneralLedgerService.post_entry(
                company_id=settlement.company_id,
                reference_type="settlement_payout",
                reference_id=str(settlement.id),
                description=f"Payout for settlement {settlement.period_label}",
                lines=[
                    {
                        "account_id": contractor_expense_account_id,
                        "debit": cls._d(settlement.net_amount),
                        "credit": 0,
                    },
                    {
                        "account_id": cash_account_id,
                        "debit": 0,
                        "credit": cls._d(settlement.net_amount),
                    },
                ],
            )

            settlement.paid = True
            settlement.payout_reference = payout["id"]

        return payout

# File: billing/stripe_connect.py
# Purpose: Stripe Connect Express integration for contractor payouts
# Status: Production-ready (Express model, SaaS-safe)
# Date: 2026-02-25

from __future__ import annotations

import os
import stripe
from typing import Optional
from decimal import Decimal
from db import db
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from models.base import Base


# ============================================================
# ENV CONFIG
# ============================================================

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PLATFORM_FEE_PERCENT = Decimal(
    os.getenv("STRIPE_PLATFORM_FEE_PERCENT", "0")
)

if not STRIPE_SECRET_KEY:
    raise RuntimeError("STRIPE_SECRET_KEY not configured")

stripe.api_key = STRIPE_SECRET_KEY


# ============================================================
# CONNECTED ACCOUNT MODEL
# ============================================================

class StripeConnectedAccount(Base):
    __tablename__ = "stripe_connected_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(nullable=False, index=True)
    contractor_id: Mapped[int] = mapped_column(nullable=False, index=True)

    stripe_account_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )

    onboarding_complete: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )


# ============================================================
# CONNECT SERVICE
# ============================================================

class StripeConnectService:

    @staticmethod
    def create_connected_account(
        *,
        company_id: int,
        contractor_id: int,
        email: str,
    ) -> StripeConnectedAccount:

        account = stripe.Account.create(
            type="express",
            country="US",
            email=email,
            capabilities={
                "transfers": {"requested": True},
            },
        )

        db_account = StripeConnectedAccount(
            company_id=company_id,
            contractor_id=contractor_id,
            stripe_account_id=account.id,
        )

        db.session.add(db_account)
        db.session.commit()

        return db_account

    @staticmethod
    def generate_onboarding_link(
        *,
        stripe_account_id: str,
        refresh_url: str,
        return_url: str,
    ) -> str:

        link = stripe.AccountLink.create(
            account=stripe_account_id,
            refresh_url=refresh_url,
            return_url=return_url,
            type="account_onboarding",
        )

        return link.url

    @staticmethod
    def check_account_status(
        *,
        stripe_account_id: str,
    ) -> bool:

        account = stripe.Account.retrieve(stripe_account_id)

        return bool(
            account.details_submitted and
            account.charges_enabled and
            account.payouts_enabled
        )

    @staticmethod
    def send_payout(
        *,
        stripe_account_id: str,
        amount: Decimal,
        currency: str = "usd",
        description: Optional[str] = None,
    ):

        amount_cents = int(Decimal(amount) * 100)

        payout = stripe.Transfer.create(
            amount=amount_cents,
            currency=currency,
            destination=stripe_account_id,
            description=description,
        )

        return payout

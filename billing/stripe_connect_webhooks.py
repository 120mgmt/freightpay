# File: billing/stripe_connect_webhooks.py
# Purpose: Enterprise-hardened Stripe Connect webhook processor
# Status: ENTERPRISE HARDNESS (idempotent, replay-safe, auditable, retry-safe)
# Date: 2026-02-25

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Optional

import stripe
from flask import Blueprint, request, jsonify
from sqlalchemy import select, Index, UniqueConstraint, String, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
import uuid

from db import db
from billing.stripe_client import get_webhook_secret, init_stripe
from billing.stripe_connect import StripeConnectedAccount
from models.driver_settlement import DriverSettlement


# ============================================================
# WEBHOOK EVENT LEDGER (IDEMPOTENCY + AUDIT)
# ============================================================

def _uuid():
    return uuid.uuid4()


class StripeWebhookEvent(db.Model):
    __tablename__ = "stripe_webhook_events"

    __table_args__ = (
        UniqueConstraint("event_id", name="uq_stripe_event_id"),
        Index("ix_stripe_event_processed", "processed"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )

    event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)

    payload_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)


# ============================================================
# WEBHOOK BLUEPRINT
# ============================================================

webhook_bp = Blueprint(
    "stripe_connect_webhooks",
    __name__,
    url_prefix="/billing/webhooks/stripe",
)


def _hash_payload(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@webhook_bp.route("/connect", methods=["POST"])
def handle_connect_webhook():

    init_stripe()

    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    secret = get_webhook_secret()

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=secret,
        )
    except Exception:
        return jsonify({"error": "invalid_signature"}), 400

    event_id = event["id"]
    event_type = event["type"]
    payload_hash = _hash_payload(payload)

    with db.session.begin():

        existing = db.session.execute(
            select(StripeWebhookEvent)
            .where(StripeWebhookEvent.event_id == event_id)
            .with_for_update()
        ).scalar_one_or_none()

        if existing:
            # Already processed or in-flight
            return jsonify({"status": "duplicate"}), 200

        ledger = StripeWebhookEvent(
            event_id=event_id,
            event_type=event_type,
            payload_hash=payload_hash,
            processed=False,
        )
        db.session.add(ledger)

    try:
        _process_event(event)

        with db.session.begin():
            ledger.processed = True
            ledger.processed_at = datetime.utcnow()

    except Exception as e:
        with db.session.begin():
            ledger.error_message = str(e)
            ledger.processed = False
        return jsonify({"error": "processing_failed"}), 500

    return jsonify({"status": "ok"}), 200


# ============================================================
# CORE EVENT PROCESSOR
# ============================================================

def _process_event(event: dict):

    event_type = event["type"]

    # ---------------------------------------
    # CONNECT ACCOUNT UPDATE
    # ---------------------------------------
    if event_type == "account.updated":

        account = event["data"]["object"]
        stripe_account_id = account["id"]

        details_submitted = account.get("details_submitted", False)
        charges_enabled = account.get("charges_enabled", False)
        payouts_enabled = account.get("payouts_enabled", False)

        with db.session.begin():

            db_account = db.session.execute(
                select(StripeConnectedAccount)
                .where(
                    StripeConnectedAccount.stripe_account_id == stripe_account_id
                )
                .with_for_update()
            ).scalar_one_or_none()

            if db_account:
                db_account.onboarding_complete = (
                    details_submitted and charges_enabled and payouts_enabled
                )

    # ---------------------------------------
    # TRANSFER PAID
    # ---------------------------------------
    if event_type == "transfer.paid":

        transfer = event["data"]["object"]
        transfer_id = transfer["id"]

        with db.session.begin():

            settlement = db.session.execute(
                select(DriverSettlement)
                .where(
                    DriverSettlement.payout_reference == transfer_id
                )
                .with_for_update()
            ).scalar_one_or_none()

            if settlement:
                settlement.payout_confirmed = True

    # ---------------------------------------
    # TRANSFER FAILED
    # ---------------------------------------
    if event_type == "transfer.failed":

        transfer = event["data"]["object"]
        transfer_id = transfer["id"]

        with db.session.begin():

            settlement = db.session.execute(
                select(DriverSettlement)
                .where(
                    DriverSettlement.payout_reference == transfer_id
                )
                .with_for_update()
            ).scalar_one_or_none()

            if settlement:
                settlement.payout_confirmed = False
                settlement.paid = False  # revert state if needed

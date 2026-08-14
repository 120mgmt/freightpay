"""create stripe_webhook_events (webhook idempotency ledger)

Revision ID: 20260419_stripe_webhook_ev
Revises: 20260418_invoice_journal
Create Date: 2026-08-14

billing/webhooks.py's _init_event_log() tried to create this table itself
with a raw "CREATE TABLE IF NOT EXISTS" at module IMPORT time — before any
Flask app context exists, so db.engine access raises "working outside of
application context", which the surrounding bare except silently swallowed.
The table was never created, so _log_event()/_event_already_processed()
have been no-ops since this webhook was written: every Stripe retry of an
already-processed event was reprocessed instead of being recognized as a
duplicate. Same columns/indexes the raw DDL specified, now created reliably
at boot like every other table in this app.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260419_stripe_webhook_ev"
down_revision = "20260418_invoice_journal"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if "stripe_webhook_events" in insp.get_table_names():
        return

    op.create_table(
        "stripe_webhook_events",
        sa.Column("event_id", sa.Text(), primary_key=True),
        sa.Column("event_type", sa.Text(), nullable=True),
        sa.Column("customer_id", sa.Text(), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("received_at", sa.BigInteger(), nullable=False),
    )
    try:
        op.create_index(
            "idx_stripe_webhook_events_customer_id",
            "stripe_webhook_events",
            ["customer_id"],
        )
    except Exception:
        pass
    try:
        op.create_index(
            "idx_stripe_webhook_events_company_id",
            "stripe_webhook_events",
            ["company_id"],
        )
    except Exception:
        pass


def downgrade():
    insp = sa.inspect(op.get_bind())
    if "stripe_webhook_events" in insp.get_table_names():
        op.drop_table("stripe_webhook_events")

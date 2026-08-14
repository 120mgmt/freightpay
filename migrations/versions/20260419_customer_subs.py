"""create customer_subscriptions (entitlement cache)

Revision ID: 20260419_customer_subs
Revises: 20260419_stripe_webhook_ev
Create Date: 2026-08-14

Same root cause as 20260419_stripe_webhook_ev, in the adjacent file:
billing/entitlement_store.py self-created this table with raw SQL at module
IMPORT time, before any Flask app context exists — db.engine access failed
and was silently swallowed. Every webhook-driven entitlement upsert and
every subscription_gate.py cache lookup has been failing since this was
written.

This degrades gracefully rather than blocking access: get_customer_subscription
catches the failure and returns None, and access checks fall back to a live
Stripe lookup (see utils/plan_access.py) — so this was a silent caching gap,
not a security hole. Still worth a real table: every plan check has been
paying for an avoidable live Stripe API round trip.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260419_customer_subs"
down_revision = "20260419_stripe_webhook_ev"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if "customer_subscriptions" in insp.get_table_names():
        return

    op.create_table(
        "customer_subscriptions",
        sa.Column("customer_id", sa.Text(), primary_key=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("subscription_id", sa.Text(), nullable=True),
        sa.Column("price_id", sa.Text(), nullable=True),
        sa.Column("price_ids_json", sa.Text(), nullable=True),
        sa.Column("current_period_end", sa.BigInteger(), nullable=True),
        sa.Column("entitlements_json", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
    )
    try:
        op.create_index(
            "idx_customer_subscriptions_updated_at",
            "customer_subscriptions",
            ["updated_at"],
        )
    except Exception:
        pass
    try:
        op.create_index(
            "idx_customer_subscriptions_subscription_id",
            "customer_subscriptions",
            ["subscription_id"],
        )
    except Exception:
        pass


def downgrade():
    insp = sa.inspect(op.get_bind())
    if "customer_subscriptions" in insp.get_table_names():
        op.drop_table("customer_subscriptions")

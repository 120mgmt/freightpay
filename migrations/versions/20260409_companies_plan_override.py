"""add companies.plan_override for manual plan assignment

Revision ID: 20260409_companies_plan_override
Revises: 20260408_seed_platform_admins
Create Date: 2026-07-16

Lets a platform admin grant a company plan access manually (comped
accounts, offline payments, testing) without a Stripe subscription.
Values: combo | payroll_only | bookkeeping_only | NULL. Idempotent.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260409_companies_plan_override"
down_revision = "20260408_seed_platform_admins"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("companies")}
    if "plan_override" not in cols:
        op.add_column(
            "companies",
            sa.Column("plan_override", sa.String(length=32), nullable=True),
        )


def downgrade():
    op.drop_column("companies", "plan_override")

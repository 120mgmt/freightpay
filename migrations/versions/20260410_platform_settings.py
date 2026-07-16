"""add platform_settings key/value table

Revision ID: 20260410_platform_settings
Revises: 20260409_companies_plan_override
Create Date: 2026-07-16

DB-backed runtime configuration managed from the admin portal. Render's
env var dashboard has repeatedly served the runtime different values
than it displays, so operational secrets (Stripe keys) move here:
written via the admin API, applied at boot and immediately in-process.
Idempotent.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260410_platform_settings"
down_revision = "20260409_companies_plan_override"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if "platform_settings" in insp.get_table_names():
        return
    op.create_table(
        "platform_settings",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade():
    op.drop_table("platform_settings")

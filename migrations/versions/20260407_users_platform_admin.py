"""add users.is_platform_admin flag

Revision ID: 20260407_users_platform_admin
Revises: 20260406_companies_columns
Create Date: 2026-07-16

Platform-admin access was governed only by the PLATFORM_ADMIN_EMAILS env
var, which the hosting dashboard repeatedly failed to persist. Store the
grant in the database instead, managed from the admin portal. Idempotent.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260407_users_platform_admin"
down_revision = "20260406_companies_columns"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("users")}

    if "is_platform_admin" not in cols:
        op.add_column(
            "users",
            sa.Column(
                "is_platform_admin",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade():
    op.drop_column("users", "is_platform_admin")

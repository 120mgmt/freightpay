# File: migrations/versions/20260216_users_email_verified.py
# Purpose: Add email_verified column to users table
# Status: Production hardened
# Date: 2026-02-16 (updated 2026-03-08)

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260216_users_email_verified"
down_revision = "20260125_compliance_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "users" not in inspector.get_table_names():
        return

    columns = [c["name"] for c in inspector.get_columns("users")]

    if "email_verified" not in columns:
        op.add_column(
            "users",
            sa.Column(
                "email_verified",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "users" not in inspector.get_table_names():
        return

    columns = [c["name"] for c in inspector.get_columns("users")]

    if "email_verified" in columns:
        op.drop_column("users", "email_verified")

# File: migrations/versions/20251231_create_users.py
# Purpose: Create base users table required by LedgerHaul auth, legal, compliance, and billing migrations
# Status: Production hardened (idempotent — safe to run against a DB where the table already exists)
# Date: 2025-12-31

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# --- Alembic identifiers ---
revision = "20251231_create_users"
down_revision = None
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    insp = _inspector()

    if "users" not in insp.get_table_names():
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False, unique=True),
            sa.Column(
                "email_verified",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column("password_hash", sa.String(length=255), nullable=True),
            sa.Column("first_name", sa.String(length=120), nullable=True),
            sa.Column("last_name", sa.String(length=120), nullable=True),
            sa.Column(
                "role",
                sa.String(length=50),
                nullable=False,
                server_default="user",
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )

    existing_indexes = {ix["name"] for ix in _inspector().get_indexes("users")}
    if "ix_users_email" not in existing_indexes:
        op.create_index(
            "ix_users_email",
            "users",
            ["email"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

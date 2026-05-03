# File: migrations/versions/20260101_add_legal_acceptances.py
# Purpose: Create legal_acceptances table (Terms/Privacy/Refund acceptance tracking)
# Status: Production hardened
# Date: 2026-01-01 (updated 2026-03-07)

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# --- Alembic identifiers ---
revision = "20260101_add_legal_acceptances"
down_revision = "20251231_create_users"
branch_labels = None
depends_on = None


def _users_table_exists() -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return "users" in inspector.get_table_names()


def upgrade() -> None:
    columns = [
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("terms_version", sa.String(length=64), nullable=False),
        sa.Column("privacy_version", sa.String(length=64), nullable=False),
        sa.Column("refund_version", sa.String(length=64), nullable=False),
        sa.Column(
            "accepted_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column(
            "is_current",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    ]

    if _users_table_exists():
        columns.append(
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="CASCADE",
                name="fk_legal_acceptances_user_id_users",
            )
        )

    op.create_table("legal_acceptances", *columns)

    op.create_index(
        "ix_legal_acceptances_user_current",
        "legal_acceptances",
        ["user_id", "is_current"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_legal_acceptances_user_current",
        table_name="legal_acceptances",
    )
    op.drop_table("legal_acceptances")

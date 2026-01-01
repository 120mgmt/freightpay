# migrations/versions/20260101_add_legal_acceptances.py
# Purpose: Create legal_acceptances table (Terms/Privacy/Refund acceptance tracking)
# Status: Full deployment – production v5
# Date: 2026-01-01

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

try:
    from sqlalchemy.dialects import postgresql
except Exception:  # pragma: no cover
    postgresql = None  # type: ignore


# --- Alembic identifiers ---
revision = "20260101_legal_acceptances"
down_revision = None  # <-- set this to your latest migration id
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Prefer Postgres UUID when available, otherwise use CHAR(36) for SQLite/local
    if postgresql is not None:
        id_type = postgresql.UUID(as_uuid=True)
        user_id_type = postgresql.UUID(as_uuid=True)
    else:
        id_type = sa.String(length=36)
        user_id_type = sa.String(length=36)

    op.create_table(
        "legal_acceptances",
        sa.Column("id", id_type, primary_key=True, nullable=False),
        sa.Column("user_id", user_id_type, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("terms_version", sa.String(), nullable=False),
        sa.Column("privacy_version", sa.String(), nullable=False),
        sa.Column("refund_version", sa.String(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=False),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_index(
        "ix_legal_acceptances_user_current",
        "legal_acceptances",
        ["user_id", "is_current"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_legal_acceptances_user_current", table_name="legal_acceptances")
    op.drop_table("legal_acceptances")

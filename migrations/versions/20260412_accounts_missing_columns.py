"""add missing accounts columns (parent_id, created_at)

Revision ID: 20260412_accounts_missing_columns
Revises: 20260411_verify_existing_users
Create Date: 2026-07-16

models/chart_of_accounts.py declares parent_id and created_at, but the
tenant COA migration created the accounts table without them, so any
ORM select on Account failed with 'column accounts.parent_id does not
exist'. Add them idempotently.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260412_accounts_cols"
down_revision = "20260411_verify_existing_users"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if "accounts" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("accounts")}

    if "parent_id" not in cols:
        op.add_column("accounts", sa.Column("parent_id", sa.Integer(), nullable=True))
        try:
            op.create_index("ix_accounts_parent_id", "accounts", ["parent_id"])
        except Exception:
            pass
        try:
            op.create_foreign_key(
                "fk_accounts_parent_id_accounts",
                "accounts", "accounts",
                ["parent_id"], ["id"],
                ondelete="SET NULL",
            )
        except Exception:
            pass

    if "created_at" not in cols:
        op.add_column(
            "accounts",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )


def downgrade():
    pass

"""add legal-acceptance columns to users

Revision ID: 20260405_users_legal_columns
Revises: 20260404_users_avatar
Create Date: 2026-07-08

models/user.py has always declared accepted_tos, accepted_privacy,
accepted_refund, and legal_accepted_at as columns on User, but no prior
migration ever added them to the users table (legal acceptance was
tracked in a separate legal_acceptances table instead). Every SELECT of
the User model includes these columns in the generated SQL, so on any
database built purely from this migration chain, EVERY query against
User — including the first line of login — fails with
"column users.accepted_tos does not exist". Idempotent.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260405_users_legal_columns"
down_revision = "20260404_users_avatar"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("users")}

    if "accepted_tos" not in cols:
        op.add_column(
            "users",
            sa.Column("accepted_tos", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "accepted_privacy" not in cols:
        op.add_column(
            "users",
            sa.Column("accepted_privacy", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "accepted_refund" not in cols:
        op.add_column(
            "users",
            sa.Column("accepted_refund", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "legal_accepted_at" not in cols:
        op.add_column("users", sa.Column("legal_accepted_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("users", "legal_accepted_at")
    op.drop_column("users", "accepted_refund")
    op.drop_column("users", "accepted_privacy")
    op.drop_column("users", "accepted_tos")

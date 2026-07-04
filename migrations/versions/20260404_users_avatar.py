"""add users.avatar_url for profile pictures

Revision ID: 20260404_users_avatar
Revises: 20260401_payroll_runs
Create Date: 2026-07-03

Stores a small data-URL image (client-side resized) so avatars work
without external object storage. Idempotent.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260404_users_avatar"
down_revision = "20260401_payroll_runs"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("users")}
    if "avatar_url" not in cols:
        op.add_column("users", sa.Column("avatar_url", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("users", "avatar_url")

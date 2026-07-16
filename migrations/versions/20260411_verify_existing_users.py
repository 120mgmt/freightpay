"""mark all existing users email_verified (email verification disabled)

Revision ID: 20260411_verify_existing_users
Revises: 20260410_platform_settings
Create Date: 2026-07-16

Email verification is now off by default, so accounts are usable at
sign-up. Backfill any accounts left unverified (created while the gate
was on) so they can sign in and show correctly in the admin portal.
Idempotent (re-running is a harmless no-op).
"""

from alembic import op
import sqlalchemy as sa

revision = "20260411_verify_existing_users"
down_revision = "20260410_platform_settings"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if "users" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "email_verified" not in cols:
        return
    op.get_bind().execute(
        sa.text("UPDATE users SET email_verified = true WHERE email_verified = false")
    )


def downgrade():
    # No-op: we do not un-verify users.
    pass

"""seed platform admin grants for the owner and developer accounts

Revision ID: 20260408_seed_platform_admins
Revises: 20260407_users_platform_admin
Create Date: 2026-07-16

The hosting dashboard repeatedly failed to persist PLATFORM_ADMIN_EMAILS,
and the first-user bootstrap targets an early test account (user id 1)
rather than the real developer account. Migrations are the one channel
that reliably reaches production, so seed the DB grants directly.

Idempotent: re-running the UPDATE is a no-op, and accounts that have not
registered yet are simply unaffected (grant them later from the admin
portal's Users tab).
"""

from alembic import op
import sqlalchemy as sa

revision = "20260408_seed_platform_admins"
down_revision = "20260407_users_platform_admin"
branch_labels = None
depends_on = None

PLATFORM_ADMIN_SEED_EMAILS = (
    "shabeershah4777@gmail.com",  # developer
    "info@ledgerhaul.com",        # owner
)


def _users_ready() -> bool:
    insp = sa.inspect(op.get_bind())
    if "users" not in insp.get_table_names():
        return False
    cols = {c["name"] for c in insp.get_columns("users")}
    return "is_platform_admin" in cols


def upgrade():
    if not _users_ready():
        return
    op.get_bind().execute(
        sa.text(
            "UPDATE users SET is_platform_admin = true "
            "WHERE lower(email) IN :emails"
        ).bindparams(sa.bindparam("emails", expanding=True)),
        {"emails": [e.lower() for e in PLATFORM_ADMIN_SEED_EMAILS]},
    )


def downgrade():
    if not _users_ready():
        return
    op.get_bind().execute(
        sa.text(
            "UPDATE users SET is_platform_admin = false "
            "WHERE lower(email) IN :emails"
        ).bindparams(sa.bindparam("emails", expanding=True)),
        {"emails": [e.lower() for e in PLATFORM_ADMIN_SEED_EMAILS]},
    )

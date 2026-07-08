"""ensure companies has stripe_customer_id and updated_at

Revision ID: 20260406_companies_columns
Revises: 20260405_users_legal_columns
Create Date: 2026-07-08

Two migrations (20260222_accounting_core and 20260308_tenant_coa_tables)
both create the companies table if it does not already exist, as siblings
off the same parent revision. Alembic may apply either branch first; on at
least one real deploy 20260308's narrower CREATE TABLE (no
stripe_customer_id, no updated_at) ran first, so 20260222's "already
exists, just add indexes" branch left the table permanently short two
columns models/company.py expects on every insert. Idempotent.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260406_companies_columns"
down_revision = "20260405_users_legal_columns"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("companies")}

    if "stripe_customer_id" not in cols:
        op.add_column("companies", sa.Column("stripe_customer_id", sa.String(length=255), nullable=True))
    if "updated_at" not in cols:
        op.add_column(
            "companies",
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        )


def downgrade():
    op.drop_column("companies", "updated_at")
    op.drop_column("companies", "stripe_customer_id")

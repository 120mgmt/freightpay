"""index journals.posted_at for the cross-tenant admin expense list

Revision ID: 20260416_journals_posted_idx
Revises: 20260415_trucking_exp_accts
Create Date: 2026-07-28

Every existing journals index is a company-scoped composite
(ix_journals_company_period, ix_journals_company_source). The platform admin
expense view orders by posted_at across all companies, which none of them serve.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260416_journals_posted_idx"
down_revision = "20260415_trucking_exp_accts"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if "journals" not in insp.get_table_names():
        return
    existing = {ix["name"] for ix in insp.get_indexes("journals")}
    if "ix_journals_posted_at" not in existing:
        try:
            op.create_index("ix_journals_posted_at", "journals", ["posted_at"])
        except Exception:
            pass


def downgrade():
    try:
        op.drop_index("ix_journals_posted_at", table_name="journals")
    except Exception:
        pass

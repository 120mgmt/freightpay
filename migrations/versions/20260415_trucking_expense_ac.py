"""backfill trucking expense categories into every existing company

Revision ID: 20260415_trucking_exp_accts
Revises: 20260414_contractor_w9
Create Date: 2026-07-28

New default accounts only reach a company when /coa/seed runs, and the UI hides
the seed button once a company has any accounts — so an established company had
no way to pick up newly added categories. This inserts them directly.

Values are hardcoded rather than imported from models.chart_of_accounts on
purpose: a migration is a frozen snapshot and must keep applying the same DDL
even if the seed template changes later.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260415_trucking_exp_accts"
down_revision = "20260414_contractor_w9"
branch_labels = None
depends_on = None


CATEGORIES = (
    ("5300", "Fuel"),
    ("5310", "Maintenance & Repairs"),
    ("5320", "Insurance"),
    ("5330", "Tolls"),
    ("5340", "Driver Pay"),
    ("5350", "Office & Admin"),
    ("5360", "Software & Subscriptions"),
    ("5370", "Load Expenses"),
    ("5380", "Permits & Licenses"),
    ("5390", "Miscellaneous"),
)


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "accounts" not in tables or "companies" not in tables:
        return

    account_cols = {c["name"] for c in insp.get_columns("accounts")}
    has_created_at = "created_at" in account_cols

    # Only companies that have already been seeded get the backfill. A company
    # with no chart of accounts at all should go through the normal seed flow so
    # it receives the full template, not just these ten rows.
    created_at_col = ", created_at" if has_created_at else ""
    created_at_val = ", now()" if has_created_at else ""

    stmt = sa.text(
        f"""
        INSERT INTO accounts
            (company_id, account_code, name, account_type, normal_balance,
             is_active, is_system{created_at_col})
        SELECT c.id, :code, :name, 'expense', 'debit', TRUE, FALSE{created_at_val}
        FROM companies c
        WHERE EXISTS (SELECT 1 FROM accounts a WHERE a.company_id = c.id)
          AND NOT EXISTS (
              SELECT 1 FROM accounts a2
              WHERE a2.company_id = c.id AND a2.account_code = :code
          )
        """
    )

    for code, name in CATEGORIES:
        bind.execute(stmt, {"code": code, "name": name})


def downgrade():
    # Leaving the accounts in place is safer than deleting them — by the time a
    # downgrade runs they may already have ledger entries posted against them
    # (ledger_entries.account_id is ON DELETE RESTRICT).
    pass

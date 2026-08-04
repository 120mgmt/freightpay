"""link a paid invoice to the journal that recognised its revenue

Revision ID: 20260418_invoice_journal
Revises: 20260417_client_invoices
Create Date: 2026-08-03

Paid invoices post a balanced journal (debit cash, credit revenue) so they
show up in the P&L. Storing the journal id makes that posting idempotent —
marking an invoice paid twice must not book the revenue twice — and lets the
posting be reversed if the invoice is later voided.

BigInteger to match journals.id.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260418_invoice_journal"
down_revision = "20260417_client_invoices"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if "client_invoices" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("client_invoices")}
    if "journal_id" not in cols:
        op.add_column("client_invoices", sa.Column("journal_id", sa.BigInteger(), nullable=True))


def downgrade():
    insp = sa.inspect(op.get_bind())
    if "client_invoices" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("client_invoices")}
    if "journal_id" in cols:
        op.drop_column("client_invoices", "journal_id")

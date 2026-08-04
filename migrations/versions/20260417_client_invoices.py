"""add client_invoices and client_invoice_items

Revision ID: 20260417_client_invoices
Revises: 20260416_journals_posted_idx
Create Date: 2026-07-28

Invoices a company sends to its own clients for services rendered. Named
client_invoices rather than invoices to keep it clearly distinct from
models/invoice.py, which models Stripe's subscription invoices for
LedgerHaul's own billing (that model has no migration and is not wired up).
"""

from alembic import op
import sqlalchemy as sa

revision = "20260417_client_invoices"
down_revision = "20260416_journals_posted_idx"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())

    if "client_invoices" not in tables:
        op.create_table(
            "client_invoices",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), nullable=False, index=True),
            sa.Column("invoice_number", sa.String(length=40), nullable=False),
            sa.Column("client_name", sa.String(length=255), nullable=False),
            sa.Column("client_email", sa.String(length=255), nullable=True),
            sa.Column("client_address", sa.Text(), nullable=True),
            sa.Column("issue_date", sa.Date(), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column(
                "status", sa.String(length=16), nullable=False, server_default="draft"
            ),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
            sa.Column("subtotal", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("tax", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("amount_paid", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("stripe_payment_link_id", sa.String(length=255), nullable=True),
            sa.Column("stripe_payment_link_url", sa.String(length=500), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint(
                "company_id", "invoice_number", name="uq_client_invoices_company_number"
            ),
            sa.CheckConstraint("total >= 0", name="ck_client_invoices_total_nonneg"),
        )
        try:
            op.create_index(
                "ix_client_invoices_company_status",
                "client_invoices",
                ["company_id", "status"],
            )
        except Exception:
            pass

    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "client_invoice_items" not in tables:
        op.create_table(
            "client_invoice_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("invoice_id", sa.Integer(), nullable=False, index=True),
            sa.Column("description", sa.String(length=500), nullable=False),
            sa.Column("quantity", sa.Numeric(12, 2), nullable=False, server_default="1"),
            sa.Column("unit_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        )
        try:
            op.create_foreign_key(
                "fk_client_invoice_items_invoice",
                "client_invoice_items",
                "client_invoices",
                ["invoice_id"],
                ["id"],
                ondelete="CASCADE",
            )
        except Exception:
            pass


def downgrade():
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    if "client_invoice_items" in tables:
        op.drop_table("client_invoice_items")
    if "client_invoices" in tables:
        op.drop_table("client_invoices")

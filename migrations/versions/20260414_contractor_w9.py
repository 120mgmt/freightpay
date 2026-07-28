"""add contractor_w9 table (uploaded document + fillable form)

Revision ID: 20260414_contractor_w9
Revises: 20260413_contractor_profile
Create Date: 2026-07-28

A contractor's W-9 can arrive two ways: the company uploads a scan/PDF they
already have, or the contractor fills the form in digitally. One row per
contractor holds either or both.

File bytes live in Postgres (bytea) rather than on disk because the host has no
persistent volume — anything written to the local filesystem is lost on the next
deploy. W-9s are small, so a bytea column is the durable option that needs no
extra infrastructure.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260414_contractor_w9"
down_revision = "20260413_contractor_profile"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "contractor_w9" in insp.get_table_names():
        return

    op.create_table(
        "contractor_w9",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("contractor_id", sa.Integer(), nullable=False),
        # "upload" | "form" — the most recent method used.
        sa.Column("method", sa.String(length=16), nullable=False, server_default="form"),
        # --- uploaded document ---
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_mime", sa.String(length=100), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("file_bytes", sa.LargeBinary(), nullable=True),
        sa.Column("file_sha256", sa.String(length=64), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        # --- fillable form ---
        sa.Column("form_name", sa.String(length=255), nullable=True),
        sa.Column("form_business_name", sa.String(length=255), nullable=True),
        sa.Column("form_tax_classification", sa.String(length=50), nullable=True),
        sa.Column("form_exempt_payee_code", sa.String(length=20), nullable=True),
        sa.Column("form_fatca_code", sa.String(length=20), nullable=True),
        sa.Column("form_address_line1", sa.String(length=255), nullable=True),
        sa.Column("form_address_line2", sa.String(length=255), nullable=True),
        sa.Column("form_city", sa.String(length=120), nullable=True),
        sa.Column("form_state", sa.String(length=50), nullable=True),
        sa.Column("form_postal_code", sa.String(length=20), nullable=True),
        sa.Column("form_requester", sa.String(length=255), nullable=True),
        sa.Column("form_account_numbers", sa.String(length=255), nullable=True),
        sa.Column("form_tin_type", sa.String(length=10), nullable=True),
        # Full TIN is stored but never returned by the API — only tin_last4 is
        # exposed, mirrored onto contractors.tin_last4.
        sa.Column("form_tin", sa.String(length=32), nullable=True),
        sa.Column("form_signature_name", sa.String(length=255), nullable=True),
        sa.Column("form_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("form_certified", sa.Boolean(), nullable=False, server_default=sa.false()),
        # --- audit ---
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
        sa.UniqueConstraint("contractor_id", name="uq_contractor_w9_contractor"),
    )

    try:
        op.create_foreign_key(
            "fk_contractor_w9_contractor",
            "contractor_w9",
            "contractors",
            ["contractor_id"],
            ["id"],
            ondelete="CASCADE",
        )
    except Exception:
        pass

    try:
        op.create_index("ix_contractor_w9_company", "contractor_w9", ["company_id"])
    except Exception:
        pass


def downgrade():
    insp = sa.inspect(op.get_bind())
    if "contractor_w9" in insp.get_table_names():
        op.drop_table("contractor_w9")

# File: migrations/versions/20260323_contractors_and_ledger_entries.py
# Purpose: Create or reconcile contractors and ledger_entries tables for 1099 + bookkeeping go-live
# Status: Enterprise hardened

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260323_ctr_ledger"
down_revision = "20260312_merge_heads"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_names(inspector, table_name: str) -> set[str]:
    return {col["name"] for col in inspector.get_columns(table_name)}


def _index_names(inspector, table_name: str) -> set[str]:
    return {idx["name"] for idx in inspector.get_indexes(table_name)}


def _unique_constraint_names(inspector, table_name: str) -> set[str]:
    names = set()
    for uq in inspector.get_unique_constraints(table_name):
        if uq.get("name"):
            names.add(uq["name"])
    return names


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # =========================
    # contractors
    # =========================
    if not _table_exists(inspector, "contractors"):
        op.create_table(
            "contractors",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column("legal_name", sa.String(length=255), nullable=False),
            sa.Column("business_name", sa.String(length=255), nullable=True),
            sa.Column("display_name", sa.String(length=255), nullable=True),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("phone", sa.String(length=50), nullable=True),
            sa.Column("address_line1", sa.String(length=255), nullable=False),
            sa.Column("address_line2", sa.String(length=255), nullable=True),
            sa.Column("city", sa.String(length=120), nullable=False),
            sa.Column("state", sa.String(length=50), nullable=False),
            sa.Column("postal_code", sa.String(length=20), nullable=False),
            sa.Column(
                "country",
                sa.String(length=2),
                nullable=False,
                server_default=sa.text("'US'"),
            ),
            sa.Column("tax_classification", sa.String(length=50), nullable=False),
            sa.Column("tin_last4", sa.String(length=4), nullable=True),
            sa.Column(
                "w9_received",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("w9_received_at", sa.DateTime(), nullable=True),
            sa.Column(
                "tin_name_match_verified",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("payment_method", sa.String(length=50), nullable=True),
            sa.Column("payment_terms", sa.String(length=50), nullable=True),
            sa.Column(
                "default_currency",
                sa.String(length=3),
                nullable=False,
                server_default=sa.text("'USD'"),
            ),
            sa.Column("default_expense_account_code", sa.String(length=32), nullable=True),
            sa.Column("default_payable_account_code", sa.String(length=32), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "onboarding_status",
                sa.String(length=50),
                nullable=False,
                server_default=sa.text("'draft'"),
            ),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
            sa.CheckConstraint("char_length(country) = 2", name="ck_contractors_country_len"),
            sa.CheckConstraint(
                "char_length(default_currency) = 3",
                name="ck_contractors_currency_len",
            ),
            sa.CheckConstraint(
                "tin_last4 IS NULL OR char_length(tin_last4) = 4",
                name="ck_contractors_tin_last4_len",
            ),
            sa.ForeignKeyConstraint(
                ["company_id"],
                ["companies.id"],
                name="fk_contractors_company",
                ondelete="CASCADE",
            ),
        )

    inspector = sa.inspect(bind)
    contractor_columns = _column_names(inspector, "contractors")
    contractor_indexes = _index_names(inspector, "contractors")
    contractor_constraints = _unique_constraint_names(inspector, "contractors")

    contractor_additions = [
        ("company_id", sa.Column("company_id", sa.Integer(), nullable=False, server_default="0")),
        ("legal_name", sa.Column("legal_name", sa.String(length=255), nullable=False, server_default="")),
        ("business_name", sa.Column("business_name", sa.String(length=255), nullable=True)),
        ("display_name", sa.Column("display_name", sa.String(length=255), nullable=True)),
        ("email", sa.Column("email", sa.String(length=255), nullable=True)),
        ("phone", sa.Column("phone", sa.String(length=50), nullable=True)),
        ("address_line1", sa.Column("address_line1", sa.String(length=255), nullable=False, server_default="")),
        ("address_line2", sa.Column("address_line2", sa.String(length=255), nullable=True)),
        ("city", sa.Column("city", sa.String(length=120), nullable=False, server_default="")),
        ("state", sa.Column("state", sa.String(length=50), nullable=False, server_default="")),
        ("postal_code", sa.Column("postal_code", sa.String(length=20), nullable=False, server_default="")),
        ("country", sa.Column("country", sa.String(length=2), nullable=False, server_default="US")),
        ("tax_classification", sa.Column("tax_classification", sa.String(length=50), nullable=False, server_default="other")),
        ("tin_last4", sa.Column("tin_last4", sa.String(length=4), nullable=True)),
        ("w9_received", sa.Column("w9_received", sa.Boolean(), nullable=False, server_default=sa.text("false"))),
        ("w9_received_at", sa.Column("w9_received_at", sa.DateTime(), nullable=True)),
        ("tin_name_match_verified", sa.Column("tin_name_match_verified", sa.Boolean(), nullable=False, server_default=sa.text("false"))),
        ("payment_method", sa.Column("payment_method", sa.String(length=50), nullable=True)),
        ("payment_terms", sa.Column("payment_terms", sa.String(length=50), nullable=True)),
        ("default_currency", sa.Column("default_currency", sa.String(length=3), nullable=False, server_default="USD")),
        ("default_expense_account_code", sa.Column("default_expense_account_code", sa.String(length=32), nullable=True)),
        ("default_payable_account_code", sa.Column("default_payable_account_code", sa.String(length=32), nullable=True)),
        ("notes", sa.Column("notes", sa.Text(), nullable=True)),
        ("is_active", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true"))),
        ("onboarding_status", sa.Column("onboarding_status", sa.String(length=50), nullable=False, server_default="draft")),
        ("deleted_at", sa.Column("deleted_at", sa.DateTime(), nullable=True)),
        ("created_at", sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))),
        ("updated_at", sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))),
        ("created_by_user_id", sa.Column("created_by_user_id", sa.Integer(), nullable=True)),
        ("updated_by_user_id", sa.Column("updated_by_user_id", sa.Integer(), nullable=True)),
    ]

    for col_name, col_def in contractor_additions:
        if col_name not in contractor_columns:
            op.add_column("contractors", col_def)

    inspector = sa.inspect(bind)
    contractor_indexes = _index_names(inspector, "contractors")
    contractor_constraints = _unique_constraint_names(inspector, "contractors")

    if "uq_contractors_company_email" not in contractor_constraints:
        op.create_unique_constraint(
            "uq_contractors_company_email",
            "contractors",
            ["company_id", "email"],
        )

    if "uq_contractors_company_legal_phone" not in contractor_constraints:
        op.create_unique_constraint(
            "uq_contractors_company_legal_phone",
            "contractors",
            ["company_id", "legal_name", "phone"],
        )

    if "ix_contractors_company_active_name" not in contractor_indexes:
        op.create_index(
            "ix_contractors_company_active_name",
            "contractors",
            ["company_id", "is_active", "legal_name"],
            unique=False,
        )

    if "ix_contractors_company_w9_status" not in contractor_indexes:
        op.create_index(
            "ix_contractors_company_w9_status",
            "contractors",
            ["company_id", "w9_received", "is_active"],
            unique=False,
        )

    if "ix_contractors_company_tax_class" not in contractor_indexes:
        op.create_index(
            "ix_contractors_company_tax_class",
            "contractors",
            ["company_id", "tax_classification"],
            unique=False,
        )

    # =========================
    # ledger_entries
    # =========================
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "ledger_entries"):
        op.create_table(
            "ledger_entries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column(
                "entry_type",
                sa.String(length=50),
                nullable=False,
                server_default=sa.text("'payroll'"),
            ),
            sa.Column("pay_period", sa.String(length=50), nullable=True),
            sa.Column("contractor_id", sa.Integer(), nullable=True),
            sa.Column("contractor_name", sa.String(length=255), nullable=True),
            sa.Column("gross", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("reimbursements", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("deductions", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("net", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("debit_account_code", sa.String(length=50), nullable=True),
            sa.Column("credit_account_code", sa.String(length=50), nullable=True),
            sa.Column("memo", sa.Text(), nullable=True),
            sa.Column("recorded_by_user_id", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(
                ["company_id"],
                ["companies.id"],
                name="fk_ledger_entries_company",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["contractor_id"],
                ["contractors.id"],
                name="fk_ledger_entries_contractor",
                ondelete="SET NULL",
            ),
        )

    inspector = sa.inspect(bind)
    ledger_columns = _column_names(inspector, "ledger_entries")
    ledger_indexes = _index_names(inspector, "ledger_entries")

    ledger_additions = [
        ("company_id", sa.Column("company_id", sa.Integer(), nullable=False, server_default="0")),
        ("entry_type", sa.Column("entry_type", sa.String(length=50), nullable=False, server_default="payroll")),
        ("pay_period", sa.Column("pay_period", sa.String(length=50), nullable=True)),
        ("contractor_id", sa.Column("contractor_id", sa.Integer(), nullable=True)),
        ("contractor_name", sa.Column("contractor_name", sa.String(length=255), nullable=True)),
        ("gross", sa.Column("gross", sa.Numeric(12, 2), nullable=False, server_default="0")),
        ("reimbursements", sa.Column("reimbursements", sa.Numeric(12, 2), nullable=False, server_default="0")),
        ("deductions", sa.Column("deductions", sa.Numeric(12, 2), nullable=False, server_default="0")),
        ("net", sa.Column("net", sa.Numeric(12, 2), nullable=False, server_default="0")),
        ("debit_account_code", sa.Column("debit_account_code", sa.String(length=50), nullable=True)),
        ("credit_account_code", sa.Column("credit_account_code", sa.String(length=50), nullable=True)),
        ("memo", sa.Column("memo", sa.Text(), nullable=True)),
        ("recorded_by_user_id", sa.Column("recorded_by_user_id", sa.Integer(), nullable=True)),
        ("created_at", sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))),
        ("updated_at", sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))),
    ]

    for col_name, col_def in ledger_additions:
        if col_name not in ledger_columns:
            op.add_column("ledger_entries", col_def)

    inspector = sa.inspect(bind)
    ledger_columns = _column_names(inspector, "ledger_entries")
    ledger_indexes = _index_names(inspector, "ledger_entries")

    if "ix_ledger_entries_company_id" not in ledger_indexes and "company_id" in ledger_columns:
        op.create_index(
            "ix_ledger_entries_company_id",
            "ledger_entries",
            ["company_id"],
            unique=False,
        )

    if (
        "ix_ledger_entries_company_created" not in ledger_indexes
        and "company_id" in ledger_columns
        and "created_at" in ledger_columns
    ):
        op.create_index(
            "ix_ledger_entries_company_created",
            "ledger_entries",
            ["company_id", "created_at"],
            unique=False,
        )

    if (
        "ix_ledger_entries_company_contractor" not in ledger_indexes
        and "company_id" in ledger_columns
        and "contractor_id" in ledger_columns
    ):
        op.create_index(
            "ix_ledger_entries_company_contractor",
            "ledger_entries",
            ["company_id", "contractor_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "ledger_entries"):
        ledger_indexes = _index_names(inspector, "ledger_entries")
        if "ix_ledger_entries_company_contractor" in ledger_indexes:
            op.drop_index("ix_ledger_entries_company_contractor", table_name="ledger_entries")
        if "ix_ledger_entries_company_created" in ledger_indexes:
            op.drop_index("ix_ledger_entries_company_created", table_name="ledger_entries")
        if "ix_ledger_entries_company_id" in ledger_indexes:
            op.drop_index("ix_ledger_entries_company_id", table_name="ledger_entries")
        op.drop_table("ledger_entries")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "contractors"):
        contractor_indexes = _index_names(inspector, "contractors")
        contractor_constraints = _unique_constraint_names(inspector, "contractors")

        if "ix_contractors_company_tax_class" in contractor_indexes:
            op.drop_index("ix_contractors_company_tax_class", table_name="contractors")
        if "ix_contractors_company_w9_status" in contractor_indexes:
            op.drop_index("ix_contractors_company_w9_status", table_name="contractors")
        if "ix_contractors_company_active_name" in contractor_indexes:
            op.drop_index("ix_contractors_company_active_name", table_name="contractors")

        if "uq_contractors_company_legal_phone" in contractor_constraints:
            op.drop_constraint("uq_contractors_company_legal_phone", "contractors", type_="unique")
        if "uq_contractors_company_email" in contractor_constraints:
            op.drop_constraint("uq_contractors_company_email", "contractors", type_="unique")

        op.drop_table("contractors")

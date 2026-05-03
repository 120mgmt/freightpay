# File: migrations/versions/20260222_accounting_core.py
# Commit: harden accounting core migration with prerequisite tenancy and coa tables

"""add hardened accounting core tables + deferred balance trigger

Revision ID: 20260222_accounting_core
Revises: 20260216_users_email_verified
Create Date: 2026-02-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260222_accounting_core"
down_revision = "20260216_users_email_verified"
branch_labels = None
depends_on = None


ACCOUNT_TYPE_ENUM = postgresql.ENUM(
    "asset",
    "liability",
    "equity",
    "revenue",
    "expense",
    name="account_type",
    create_type=False,
)

NORMAL_BALANCE_ENUM = postgresql.ENUM(
    "debit",
    "credit",
    name="normal_balance",
    create_type=False,
)


def _bind() -> sa.engine.Connection:
    return op.get_bind()


def _inspector() -> sa.Inspector:
    return sa.inspect(_bind())


def _table_exists(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return column_name in {col["name"] for col in _inspector().get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return index_name in {idx["name"] for idx in _inspector().get_indexes(table_name)}


def _fk_exists(table_name: str, fk_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return fk_name in {
        fk["name"]
        for fk in _inspector().get_foreign_keys(table_name)
        if fk.get("name")
    }


def _unique_constraint_exists(table_name: str, constraint_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return constraint_name in {
        uq["name"]
        for uq in _inspector().get_unique_constraints(table_name)
        if uq.get("name")
    }


def _check_constraint_exists(table_name: str, constraint_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    try:
        checks = _inspector().get_check_constraints(table_name)
    except NotImplementedError:
        return False
    return constraint_name in {
        ck["name"]
        for ck in checks
        if ck.get("name")
    }


def _safe_create_index(
    table_name: str,
    index_name: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    if not _table_exists(table_name):
        return
    for col in columns:
        if not _column_exists(table_name, col):
            return
    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def _safe_drop_index(index_name: str, *, table_name: str) -> None:
    if _index_exists(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def _safe_drop_table(table_name: str) -> None:
    if _table_exists(table_name):
        op.drop_table(table_name)


def _safe_drop_constraint(
    table_name: str,
    constraint_name: str,
    *,
    constraint_type: str,
) -> None:
    if constraint_type == "foreignkey" and _fk_exists(table_name, constraint_name):
        op.drop_constraint(constraint_name, table_name, type_=constraint_type)
        return

    if constraint_type == "unique" and _unique_constraint_exists(table_name, constraint_name):
        op.drop_constraint(constraint_name, table_name, type_=constraint_type)
        return

    if constraint_type == "check" and _check_constraint_exists(table_name, constraint_name):
        op.drop_constraint(constraint_name, table_name, type_=constraint_type)


def _create_companies_table() -> None:
    if _table_exists("companies"):
        _safe_create_index("companies", "ix_companies_slug", ["slug"], unique=True)
        _safe_create_index("companies", "ix_companies_active", ["is_active"], unique=False)
        return

    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("slug", name="uq_companies_slug"),
    )

    _safe_create_index("companies", "ix_companies_slug", ["slug"], unique=True)
    _safe_create_index("companies", "ix_companies_active", ["is_active"], unique=False)
    


def _ensure_default_company() -> int:
    bind = _bind()

    company_id = bind.execute(
        sa.text("SELECT id FROM companies WHERE slug = :slug LIMIT 1"),
        {"slug": "default"},
    ).scalar()

    if company_id is not None:
        return int(company_id)

    bind.execute(
        sa.text(
            """
            INSERT INTO companies (name, slug, is_active, created_at, updated_at)
            VALUES (:name, :slug, true, now(), now())
            """
        ),
        {"name": "Default Company", "slug": "default"},
    )

    company_id = bind.execute(
        sa.text("SELECT id FROM companies WHERE slug = :slug LIMIT 1"),
        {"slug": "default"},
    ).scalar()

    if company_id is None:
        raise RuntimeError("Failed to create or fetch default company record.")

    return int(company_id)


def _ensure_users_company_id(default_company_id: int) -> None:
    if not _table_exists("users"):
        return

    if not _column_exists("users", "company_id"):
        op.add_column("users", sa.Column("company_id", sa.Integer(), nullable=True))

    bind = _bind()
    bind.execute(
        sa.text(
            """
            UPDATE users
            SET company_id = :company_id
            WHERE company_id IS NULL
            """
        ),
        {"company_id": default_company_id},
    )

    if not _fk_exists("users", "fk_users_company_id_companies"):
        op.create_foreign_key(
            "fk_users_company_id_companies",
            "users",
            "companies",
            ["company_id"],
            ["id"],
            ondelete="CASCADE",
        )

    _safe_create_index("users", "ix_users_company_id", ["company_id"], unique=False)

    op.alter_column("users", "company_id", existing_type=sa.Integer(), nullable=False)


def _create_accounts_table() -> None:
    bind = _bind()

    ACCOUNT_TYPE_ENUM.create(bind, checkfirst=True)
    NORMAL_BALANCE_ENUM.create(bind, checkfirst=True)

    if _table_exists("accounts"):
        _ensure_accounts_table_supporting_objects()
        return

    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("account_code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("account_type", ACCOUNT_TYPE_ENUM, nullable=False),
        sa.Column("normal_balance", NORMAL_BALANCE_ENUM, nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_accounts_company_id_companies",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["accounts.id"],
            name="fk_accounts_parent_id_accounts",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("company_id", "account_code", name="uq_accounts_company_code"),
        sa.CheckConstraint("length(account_code) > 0", name="ck_account_code_nonempty"),
        sa.CheckConstraint("length(name) > 0", name="ck_account_name_nonempty"),
    )

    _ensure_accounts_table_supporting_objects()


def _ensure_accounts_table_supporting_objects() -> None:
    if not _table_exists("accounts"):
        return

    _safe_create_index("accounts", "ix_accounts_company_id", ["company_id"], unique=False)
    _safe_create_index(
        "accounts",
        "ix_accounts_company_type",
        ["company_id", "account_type"],
        unique=False,
    )


def _create_journals_table() -> None:
    if _table_exists("journals"):
        _ensure_journals_table_supporting_objects()
        return

    op.create_table(
        "journals",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("accounting_period", sa.String(length=7), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("posted_by", sa.Integer(), nullable=True),
        sa.Column("is_reversal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("reversed_journal_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_journals_company_id_companies",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["posted_by"],
            ["users.id"],
            name="fk_journals_posted_by_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reversed_journal_id"],
            ["journals.id"],
            name="fk_journals_reversed_journal_id_journals",
            ondelete="SET NULL",
        ),
    )

    _ensure_journals_table_supporting_objects()


def _ensure_journals_table_supporting_objects() -> None:
    if not _table_exists("journals"):
        return

    _safe_create_index(
        "journals",
        "ix_journals_company_period",
        ["company_id", "accounting_period"],
        unique=False,
    )
    _safe_create_index(
        "journals",
        "ix_journals_company_source",
        ["company_id", "source_type", "source_id"],
        unique=False,
    )


def _create_ledger_entries_table() -> None:
    if _table_exists("ledger_entries"):
        _ensure_ledger_entries_table_supporting_objects()
        return

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("journal_id", sa.BigInteger(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("account_code", sa.String(length=50), nullable=False),
        sa.Column("debit", sa.Numeric(14, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("credit", sa.Numeric(14, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default=sa.text("'USD'"), nullable=False),
        sa.Column("memo", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_ledger_entries_company_id_companies",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["journal_id"],
            ["journals.id"],
            name="fk_ledger_entries_journal_id_journals",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_ledger_entries_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "(debit = 0 AND credit > 0) OR (credit = 0 AND debit > 0)",
            name="ck_ledger_debit_credit_exclusive",
        ),
        sa.CheckConstraint(
            "debit >= 0 AND credit >= 0",
            name="ck_ledger_non_negative_amounts",
        ),
    )

    _ensure_ledger_entries_table_supporting_objects()


def _ensure_ledger_entries_table_supporting_objects() -> None:
    if not _table_exists("ledger_entries"):
        return

    _safe_create_index(
        "ledger_entries",
        "ix_ledger_company_account",
        ["company_id", "account_id"],
        unique=False,
    )
    _safe_create_index(
        "ledger_entries",
        "ix_ledger_company_journal",
        ["company_id", "journal_id"],
        unique=False,
    )
    _safe_create_index(
        "ledger_entries",
        "ix_ledger_company_created",
        ["company_id", "created_at"],
        unique=False,
    )


def _create_balance_functions_and_trigger() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_journal_balanced(_journal_id bigint)
        RETURNS void
        LANGUAGE plpgsql
        AS $$
        DECLARE
            d numeric(14,2);
            c numeric(14,2);
        BEGIN
            SELECT
                COALESCE(SUM(debit), 0.00),
                COALESCE(SUM(credit), 0.00)
            INTO d, c
            FROM ledger_entries
            WHERE journal_id = _journal_id;

            IF d <> c THEN
                RAISE EXCEPTION 'UNBALANCED_JOURNAL:% (debits=% credits=%)', _journal_id, d, c;
            END IF;
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_enforce_journal_balanced()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            j bigint;
        BEGIN
            j := COALESCE(NEW.journal_id, OLD.journal_id);
            PERFORM enforce_journal_balanced(j);
            RETURN NULL;
        END;
        $$;
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS ledger_entries_balance_trigger ON ledger_entries;
        CREATE CONSTRAINT TRIGGER ledger_entries_balance_trigger
        AFTER INSERT OR UPDATE OR DELETE ON ledger_entries
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION trg_enforce_journal_balanced();
        """
    )


def _drop_balance_functions_and_trigger() -> None:
    if _table_exists("ledger_entries"):
        op.execute("DROP TRIGGER IF EXISTS ledger_entries_balance_trigger ON ledger_entries;")
    op.execute("DROP FUNCTION IF EXISTS trg_enforce_journal_balanced();")
    op.execute("DROP FUNCTION IF EXISTS enforce_journal_balanced(bigint);")


def _drop_ledger_entries_table() -> None:
    _safe_drop_index("ix_ledger_company_created", table_name="ledger_entries")
    _safe_drop_index("ix_ledger_company_journal", table_name="ledger_entries")
    _safe_drop_index("ix_ledger_company_account", table_name="ledger_entries")
    _safe_drop_table("ledger_entries")


def _drop_journals_table() -> None:
    _safe_drop_index("ix_journals_company_source", table_name="journals")
    _safe_drop_index("ix_journals_company_period", table_name="journals")
    _safe_drop_table("journals")


def _drop_accounts_table() -> None:
    _safe_drop_index("ix_accounts_company_type", table_name="accounts")
    _safe_drop_index("ix_accounts_company_id", table_name="accounts")
    _safe_drop_table("accounts")


def _drop_users_company_id() -> None:
    if not _table_exists("users"):
        return

    _safe_drop_index("ix_users_company_id", table_name="users")
    _safe_drop_constraint(
        "users",
        "fk_users_company_id_companies",
        constraint_type="foreignkey",
    )

    if _column_exists("users", "company_id"):
        op.drop_column("users", "company_id")


def _drop_companies_table() -> None:
    _safe_drop_index("ix_companies_active", table_name="companies")
    _safe_drop_index("ix_companies_slug", table_name="companies")
    _safe_drop_table("companies")


def _drop_accounting_enums() -> None:
    bind = _bind()
    NORMAL_BALANCE_ENUM.drop(bind, checkfirst=True)
    ACCOUNT_TYPE_ENUM.drop(bind, checkfirst=True)


def upgrade() -> None:
    _create_companies_table()

    default_company_id = _ensure_default_company()

    _ensure_users_company_id(default_company_id)

    _create_accounts_table()
    _create_journals_table()
    _create_ledger_entries_table()

    _create_balance_functions_and_trigger()


def downgrade() -> None:
    _drop_balance_functions_and_trigger()

    _drop_ledger_entries_table()
    _drop_journals_table()
    _drop_accounts_table()

    _drop_users_company_id()
    _drop_companies_table()

    _drop_accounting_enums()

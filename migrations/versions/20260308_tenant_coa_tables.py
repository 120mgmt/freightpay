# migrations/versions/20260308_tenant_coa_tables.py
# Purpose: Create tenant companies table and base accounts table required before accounting_core
# Status: Enterprise Hardened
# Date: 2026-03-08

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260308_tenant_coa_tables"
down_revision = "20260216_users_email_verified"
branch_labels = None
depends_on = None


def _ensure_pg_enum(name: str, values: tuple[str, ...]) -> None:
    """Create PostgreSQL enum type only if it does not exist (idempotent)."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        sa.Enum(*values, name=name).create(bind, checkfirst=True)
        return
    # Build DDL in Python so no bound param is used in CREATE TYPE path (avoids
    # psycopg IndeterminateDatatype for $1). Identifiers and literals are from
    # migration constants only.
    safe_name_literal = name.replace("'", "''")
    quoted_ident = '"' + name.replace('"', '""') + '"'
    values_literals = ", ".join(f"'{v.replace(chr(39), chr(39) + chr(39))}'" for v in values)
    create_sql = f"CREATE TYPE {quoted_ident} AS ENUM ({values_literals})"
    create_sql_escaped = create_sql.replace("'", "''")
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                EXECUTE '{create_sql_escaped}';
            EXCEPTION
                WHEN duplicate_object THEN
                    NULL;
            END
            $$;
            """
        )
    )


def upgrade() -> None:

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_tables = inspector.get_table_names()

    if "companies" not in existing_tables:

        op.create_table(
            "companies",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("slug", sa.String(160), nullable=False, unique=True),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )

    existing_tables = inspector.get_table_names()

    if "users" in existing_tables:

        user_columns = [c["name"] for c in inspector.get_columns("users")]

        if "company_id" not in user_columns:
            op.add_column(
                "users",
                sa.Column("company_id", sa.Integer(), nullable=True),
            )

        fk_names = [fk["name"] for fk in inspector.get_foreign_keys("users")]

        if "fk_users_company" not in fk_names:
            op.create_foreign_key(
                "fk_users_company",
                "users",
                "companies",
                ["company_id"],
                ["id"],
                ondelete="CASCADE",
            )

    existing_tables = inspector.get_table_names()

    if "accounts" not in existing_tables:

        _ensure_pg_enum(
            "account_type",
            ("asset", "liability", "equity", "revenue", "expense"),
        )
        _ensure_pg_enum("normal_balance", ("debit", "credit"))

        account_type_enum = postgresql.ENUM(
            "asset",
            "liability",
            "equity",
            "revenue",
            "expense",
            name="account_type",
            create_type=False,
        )
        normal_balance_enum = postgresql.ENUM(
            "debit",
            "credit",
            name="normal_balance",
            create_type=False,
        )

        op.create_table(
            "accounts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "company_id",
                sa.Integer(),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "account_code",
                sa.String(50),
                nullable=False,
            ),
            sa.Column(
                "name",
                sa.String(120),
                nullable=False,
            ),
            sa.Column(
                "account_type",
                account_type_enum,
                nullable=False,
            ),
            sa.Column(
                "normal_balance",
                normal_balance_enum,
                nullable=False,
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "is_system",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.UniqueConstraint(
                "company_id",
                "account_code",
                name="uq_accounts_company_code",
            ),
        )


def downgrade() -> None:

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_tables = inspector.get_table_names()

    if "accounts" in existing_tables:
        op.drop_table("accounts")

    if "users" in existing_tables:

        user_columns = [c["name"] for c in inspector.get_columns("users")]

        if "company_id" in user_columns:
            op.drop_constraint(
                "fk_users_company",
                "users",
                type_="foreignkey",
            )
            op.drop_column("users", "company_id")

    if "companies" in existing_tables:
        op.drop_table("companies")

    sa.Enum(
        "asset",
        "liability",
        "equity",
        "revenue",
        "expense",
        name="account_type",
    ).drop(bind, checkfirst=True)

    sa.Enum(
        "debit",
        "credit",
        name="normal_balance",
    ).drop(bind, checkfirst=True)
    # Note: If downgrade fails with "cannot drop type because other objects depend on it",
    # drop dependent tables first or run: DROP TYPE IF EXISTS normal_balance CASCADE;
    # DROP TYPE IF EXISTS account_type CASCADE;
# migrations/versions/20260125_compliance_tables.py
# Purpose: Create compliance legal document tables
# Status: Enterprise hardened – CI-safe users dependency
# Date: 2026-01-25 (updated 2026-03-07)

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260125_compliance_tables"
down_revision = "20260101_add_legal_acceptances"
branch_labels = None
depends_on = None


def _users_table_exists() -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return "users" in inspector.get_table_names()


def upgrade() -> None:
    op.create_table(
        "legal_documents",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("doc_key", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "doc_key",
            "version",
            name="uq_legal_documents_doc_key_version",
        ),
    )

    op.create_index(
        "ix_legal_documents_doc_key",
        "legal_documents",
        ["doc_key"],
        unique=False,
    )
    op.create_index(
        "ix_legal_documents_is_active",
        "legal_documents",
        ["is_active"],
        unique=False,
    )

    acceptance_columns = [
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("doc_key", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id",
            "doc_key",
            "version",
            name="uq_user_legal_acceptance",
        ),
    ]

    if _users_table_exists():
        acceptance_columns.append(
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="CASCADE",
                name="fk_user_legal_acceptances_user_id_users",
            )
        )

    op.create_table("user_legal_acceptances", *acceptance_columns)

    op.create_index(
        "ix_user_legal_acceptances_user_id",
        "user_legal_acceptances",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_legal_acceptances_doc_key",
        "user_legal_acceptances",
        ["doc_key"],
        unique=False,
    )
    op.create_index(
        "ix_user_legal_acceptances_accepted",
        "user_legal_acceptances",
        ["accepted"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_legal_acceptances_accepted",
        table_name="user_legal_acceptances",
    )
    op.drop_index(
        "ix_user_legal_acceptances_doc_key",
        table_name="user_legal_acceptances",
    )
    op.drop_index(
        "ix_user_legal_acceptances_user_id",
        table_name="user_legal_acceptances",
    )
    op.drop_table("user_legal_acceptances")

    op.drop_index(
        "ix_legal_documents_is_active",
        table_name="legal_documents",
    )
    op.drop_index(
        "ix_legal_documents_doc_key",
        table_name="legal_documents",
    )
    op.drop_table("legal_documents")

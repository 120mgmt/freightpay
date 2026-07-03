"""add payroll_runs table

Revision ID: 20260401_payroll_runs
Revises: 20260323_contractors_and_ledger_entries
Create Date: 2026-04-01

Idempotent: skips creation when the table already exists (the follow-up
revision 20260403_payroll_runs_v2 reconciles the schema either way).
"""

from alembic import op
import sqlalchemy as sa

revision = "20260401_payroll_runs"
down_revision = "20260323_ctr_ledger"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if "payroll_runs" in insp.get_table_names():
        return

    op.create_table(
        "payroll_runs",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("results_json", sa.Text(), nullable=True),
        sa.Column("finalized", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("finalized_at", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(
        "idx_payroll_runs_company_created",
        "payroll_runs",
        ["company_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_payroll_runs_company_status",
        "payroll_runs",
        ["company_id", "status"],
    )


def downgrade():
    op.drop_index("idx_payroll_runs_company_status", table_name="payroll_runs")
    op.drop_index("idx_payroll_runs_company_created", table_name="payroll_runs")
    op.drop_table("payroll_runs")

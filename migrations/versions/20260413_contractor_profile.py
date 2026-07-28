"""add contractor pay-rate and truck/equipment columns

Revision ID: 20260413_contractor_profile
Revises: 20260412_accounts_cols
Create Date: 2026-07-28

Contractor profiles could store identity, address and tax details but had no
pay rate and no equipment information — pay amounts only existed inside each
payroll run's JSON payload. These columns let a company store a driver's
standing pay arrangement and truck once instead of retyping it every run.

rate_per_mile is Numeric(8,4): per-mile rates are quoted to 3-4 decimals
($0.655/mi) and rounding them to cents materially changes a settlement.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260413_contractor_profile"
down_revision = "20260412_accounts_cols"
branch_labels = None
depends_on = None


NEW_COLUMNS = (
    ("pay_type", sa.String(length=20)),
    ("rate_per_mile", sa.Numeric(8, 4)),
    ("flat_rate_per_load", sa.Numeric(12, 2)),
    ("percentage_of_load", sa.Numeric(5, 2)),
    ("hourly_rate", sa.Numeric(10, 2)),
    ("truck_number", sa.String(length=50)),
    ("truck_vin", sa.String(length=17)),
    ("truck_plate", sa.String(length=20)),
    ("trailer_number", sa.String(length=50)),
)


def upgrade():
    insp = sa.inspect(op.get_bind())
    if "contractors" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("contractors")}

    for name, coltype in NEW_COLUMNS:
        if name not in cols:
            op.add_column("contractors", sa.Column(name, coltype, nullable=True))


def downgrade():
    insp = sa.inspect(op.get_bind())
    if "contractors" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("contractors")}
    for name, _ in NEW_COLUMNS:
        if name in cols:
            op.drop_column("contractors", name)

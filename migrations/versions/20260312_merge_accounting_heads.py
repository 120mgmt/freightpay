# File: migrations/versions/20260312_merge_accounting_heads.py
# Purpose: Merge two Alembic heads (20260222_accounting_core, 20260308_tenant_coa_tables)
# Status: Production-safe
# Date: 2026-03-12
#
# Migration conflict review: 20260222 and 20260308 both have down_revision = "20260216_users_email_verified",
# creating two heads. This merge revision is the single successor; run "flask db upgrade" to apply the full
# chain (20260216 -> 20260222, 20260216 -> 20260308, then this merge). No schema change in this revision.

"""merge accounting and tenant_coa migration heads

Revision ID: 20260312_merge_heads
Revises: 20260222_accounting_core, 20260308_tenant_coa_tables
Create Date: 2026-03-12

"""

from __future__ import annotations

from alembic import op


revision = "20260312_merge_heads"
down_revision = ("20260222_accounting_core", "20260308_tenant_coa_tables")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

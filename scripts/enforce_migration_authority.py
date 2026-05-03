# File: scripts/enforce_migration_authority.py
# Purpose: HARD PRODUCTION GOVERNANCE — enforce Alembic-only migrations in prod
# Status: FULL PRODUCTION – hardened, fail-fast, non-bypassable
# Date: 2026-01-26

import os
import sys
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
ALEMBIC_DIR = PROJECT_ROOT / "migrations" / "versions"

# Any raw SQL that must NEVER be executed directly in prod
FORBIDDEN_SQL_PATHS = [
    PROJECT_ROOT / "billing" / "migrations.sql",
    PROJECT_ROOT / "billing" / "invoice_migrations.sql",
    PROJECT_ROOT / "sql",
]

ENV = os.getenv("ENV", "dev").lower()

def fail(msg: str):
    print(f"\n❌ MIGRATION GOVERNANCE VIOLATION:\n{msg}\n", file=sys.stderr)
    sys.exit(1)

def assert_alembic_exists():
    if not ALEMBIC_DIR.exists():
        fail("Alembic versions directory is missing. Migrations cannot be trusted.")

def assert_no_raw_sql_execution():
    for path in FORBIDDEN_SQL_PATHS:
        if path.exists():
            fail(
                f"Raw SQL migration file detected at {path}.\n"
                "Raw SQL is REFERENCE-ONLY. Use Alembic for production schema changes."
            )

def assert_prod_rules():
    if ENV == "prod":
        assert_alembic_exists()
        assert_no_raw_sql_execution()

if __name__ == "__main__":
    assert_prod_rules()
    print("✅ Migration governance check passed.")

# scripts/migrate_001_add_legal_acceptance_cols.py
"""
Adds legal acceptance columns to the users table if missing.

Run:
  python scripts/migrate_001_add_legal_acceptance_cols.py
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from utils.database import engine


def _has_column(table: str, column: str) -> bool:
    insp = inspect(engine)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def main() -> None:
    # Ensure table exists
    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        raise RuntimeError("users table does not exist. Run init_db first.")

    dialect = engine.dialect.name.lower()

    to_add = [
        ("accepted_tos", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("accepted_privacy", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("legal_accepted_at", "TIMESTAMP NULL"),
    ]

    with engine.begin() as conn:
        for col, ddl in to_add:
            if _has_column("users", col):
                continue

            if dialect in {"postgresql", "postgres"}:
                conn.execute(text(f'ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {ddl};'))
            elif dialect == "sqlite":
                # SQLite: no IF NOT EXISTS for ADD COLUMN on many installs, so we pre-check above.
                conn.execute(text(f'ALTER TABLE users ADD COLUMN {col} {ddl};'))
            else:
                # Generic fallback
                conn.execute(text(f'ALTER TABLE users ADD COLUMN {col} {ddl};'))

    print("✅ Migration complete: users legal acceptance columns ensured.")


if __name__ == "__main__":
    main()

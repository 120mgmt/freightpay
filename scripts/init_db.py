# scripts/init_db.py
"""
Local/development database bootstrap.

Usage:
  python scripts/init_db.py

Behavior:
- Loads the live Flask app configuration and SQLAlchemy metadata.
- Creates all tables for local/dev bootstrap only.
- Refuses to run in production.
- Does not replace migrations for production schema changes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _is_production() -> bool:
    app_env = os.getenv("APP_ENV", "production").strip().lower()
    render_flag = os.getenv("RENDER", "").strip().lower() == "true"
    return app_env == "production" or render_flag


def main() -> None:
    if _is_production():
        raise RuntimeError(
            "scripts/init_db.py is disabled in production. "
            "Use migrations for production schema changes."
        )

    from app import app  # noqa: E402
    from db import db  # noqa: E402

    with app.app_context():
        db.create_all()

        table_names = sorted(db.metadata.tables.keys())
        print("Database initialized. Tables:")
        for name in table_names:
            print(f" - {name}")


if __name__ == "__main__":
    main()

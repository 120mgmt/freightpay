# scripts/init_db.py
"""
Initialize the database schema (create all tables).

Run:
  python scripts/init_db.py

Notes:
- This uses your configured DATABASE_URL (Render Postgres) or falls back to sqlite:///freightpay.db.
- It imports all models to ensure tables are registered before create_all().
"""

from __future__ import annotations

import sys

# Ensure project root is on sys.path when running as a script
# (so "models" / "utils" imports work reliably)
if "" not in sys.path:
    sys.path.insert(0, "")

from utils.database import engine  # noqa: E402


def _import_models() -> None:
    """
    Import models so SQLAlchemy registers all mapped classes before create_all().
    Keep imports explicit to avoid missing tables.
    """
    # Core
    from models.company import Company  # noqa: F401
    from models.user import User  # noqa: F401
    from models.driver import Driver  # noqa: F401
    from models.payroll_run import PayrollRun  # noqa: F401
    from models.settlement import Settlement  # noqa: F401
    from models.legal_acceptance import LegalAcceptance  # noqa: F401

    # If you add new models later, add them here.


def _get_models_base():
    """
    Prefer the Base used by your models package.
    Falls back safely if structure differs.
    """
    try:
        from models.base import Base  # type: ignore
        return Base
    except Exception:
        from utils.database import Base  # type: ignore
        return Base


def main() -> None:
    _import_models()
    Base = _get_models_base()

    Base.metadata.create_all(bind=engine)

    table_names = sorted(list(Base.metadata.tables.keys()))
    print("✅ Database initialized. Tables:")
    for t in table_names:
        print(f" - {t}")


if __name__ == "__main__":
    main()

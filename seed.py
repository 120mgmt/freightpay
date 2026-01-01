# freightpay/seed.py
# Purpose: Central seed runner (includes legal seeding)
# Status: Full deployment – production v5
# Date: 2026-01-01

from __future__ import annotations

from sqlalchemy.orm import Session

from utils.database import get_db
from freightpay.legal.seed import seed_legal_versions


def run_seeds() -> None:
    """
    Called by: flask --app freightpay:create_app seed
    """
    db: Session = get_db()

    # Legal (version guards)
    seed_legal_versions(db)

    db.commit()

# freightpay/seed.py
# Purpose: Central seed runner (includes legal seeding)
# Status: Full deployment – production v5
# Date: 2026-01-01

from __future__ import annotations

from sqlalchemy.orm import Session

from db import db
from legal.seed import seed_legal_versions


def run_seeds(session: Session | None = None) -> None:
    """
    Seed runner.
    NOTE: Must be executed inside an active Flask app context if `session` is not provided.
    """
    s: Session = session or db.session

    # Legal (version guards)
    seed_legal_versions(s)

    s.commit()

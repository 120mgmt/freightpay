# freightpay/legal/seed.py
# Purpose: Seed initial legal versions (deployment safety)
# Status: Full deployment – production v5
# Date: 2026-01-01

from __future__ import annotations

from sqlalchemy.orm import Session

from freightpay.legal.service import (
    CURRENT_TERMS_VERSION,
    CURRENT_PRIVACY_VERSION,
    CURRENT_REFUND_VERSION,
)


def seed_legal_versions(db: Session) -> None:
    """
    Deployment guard:
    Ensures current legal versions are defined and importable
    at runtime. No DB rows are created here; this is intentional.
    """

    assert CURRENT_TERMS_VERSION
    assert CURRENT_PRIVACY_VERSION
    assert CURRENT_REFUND_VERSION

# freightpay/legal/service.py
# Purpose: Legal acceptance enforcement + persistence logic
# Status: Full deployment – production v5
# Date: 2026-01-01

from __future__ import annotations

from sqlalchemy.orm import Session

from legal.models import LegalAcceptance
from models import User


CURRENT_TERMS_VERSION = "v1.0"
CURRENT_PRIVACY_VERSION = "v1.0"
CURRENT_REFUND_VERSION = "v1.0"


def has_current_legal_acceptance(db: Session, user: User) -> bool:
    return (
        db.query(LegalAcceptance)
        .filter(
            LegalAcceptance.user_id == user.id,
            LegalAcceptance.is_current.is_(True),
            LegalAcceptance.terms_version == CURRENT_TERMS_VERSION,
            LegalAcceptance.privacy_version == CURRENT_PRIVACY_VERSION,
            LegalAcceptance.refund_version == CURRENT_REFUND_VERSION,
        )
        .first()
        is not None
    )


def record_legal_acceptance(
    *,
    db: Session,
    user: User,
    ip_address: str | None,
    user_agent: str | None,
) -> LegalAcceptance:

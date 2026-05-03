# File: legal/service.py
# Purpose: Legal versions + acceptance service layer (uses constants + legal_acceptances table)
# Status: Enterprise hardened
# Date: 2026-03-05

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from db import db
from legal.models import LegalAcceptance

# Version identifiers for seed/deployment (legal/seed.py imports these)
CURRENT_TERMS_VERSION = "1"
CURRENT_PRIVACY_VERSION = "1"
CURRENT_REFUND_VERSION = "1"


class LegalServiceError(Exception):
    pass


def _session() -> Session:
    return db.session


def get_required_versions(session: Session | None = None) -> dict[str, str]:
    """Return current required version strings (from constants; no legal_versions table)."""
    return {
        "terms": CURRENT_TERMS_VERSION,
        "privacy": CURRENT_PRIVACY_VERSION,
        "refund": CURRENT_REFUND_VERSION,
    }


def user_has_accepted_current(
    *,
    user_id: str | int,
    session: Session | None = None,
) -> bool:
    s = session or _session()
    required = get_required_versions(session=s)

    stmt = (
        select(LegalAcceptance)
        .where(
            LegalAcceptance.user_id == user_id,
            LegalAcceptance.is_current.is_(True),
        )
    )
    row = s.execute(stmt).scalar_one_or_none()
    if row is None:
        return False

    return (
        row.terms_version == required["terms"]
        and row.privacy_version == required["privacy"]
        and row.refund_version == required["refund"]
    )


def has_current_legal_acceptance(session: Session, user: Any) -> bool:
    user_id = getattr(user, "id", None)
    if user_id is None:
        return False
    return user_has_accepted_current(user_id=user_id, session=session)


def _get_or_create_current_acceptance(
    user_id: int,
    session: Session,
) -> LegalAcceptance:
    stmt = select(LegalAcceptance).where(
        LegalAcceptance.user_id == user_id,
        LegalAcceptance.is_current.is_(True),
    )
    row = session.execute(stmt).scalar_one_or_none()
    if row is not None:
        return row
    row = LegalAcceptance(
        user_id=user_id,
        terms_version=CURRENT_TERMS_VERSION,
        privacy_version=CURRENT_PRIVACY_VERSION,
        refund_version=CURRENT_REFUND_VERSION,
        is_current=True,
    )
    session.add(row)
    return row


def record_acceptance(
    *,
    user_id: str | int,
    doc_type: str,
    legal_version_id: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    accepted: bool = True,
    session: Session | None = None,
) -> LegalAcceptance:
    """Record acceptance for one doc type; updates the user's current acceptance row."""
    s = session or _session()
    user_id = int(user_id)

    version_map = {
        "terms": CURRENT_TERMS_VERSION,
        "privacy": CURRENT_PRIVACY_VERSION,
        "refund": CURRENT_REFUND_VERSION,
    }
    if doc_type not in version_map:
        raise LegalServiceError(f"Unknown doc_type: {doc_type}")

    row = _get_or_create_current_acceptance(user_id, s)
    if doc_type == "terms":
        row.terms_version = version_map["terms"]
    elif doc_type == "privacy":
        row.privacy_version = version_map["privacy"]
    else:
        row.refund_version = version_map["refund"]

    row.accepted_at = datetime.utcnow()
    if ip_address is not None:
        row.ip_address = ip_address
    if user_agent is not None:
        row.user_agent = user_agent
    s.commit()
    return row


def record_full_acceptance_bundle(
    *,
    user_id: str | int,
    ip_address: str | None = None,
    user_agent: str | None = None,
    session: Session | None = None,
) -> dict[str, LegalAcceptance]:
    s = session or _session()
    user_id = int(user_id)

    required = get_required_versions(session=s)
    if not required["terms"] or not required["privacy"] or not required["refund"]:
        raise LegalServiceError("Missing required legal versions (constants not set)")

    # Mark any existing current row as not current, then create/update one current row
    existing = s.execute(
        select(LegalAcceptance).where(
            LegalAcceptance.user_id == user_id,
            LegalAcceptance.is_current.is_(True),
        )
    ).scalar_one_or_none()
    if existing:
        existing.is_current = False

    row = LegalAcceptance(
        user_id=user_id,
        terms_version=required["terms"],
        privacy_version=required["privacy"],
        refund_version=required["refund"],
        accepted_at=datetime.utcnow(),
        ip_address=ip_address,
        user_agent=user_agent,
        is_current=True,
    )
    s.add(row)
    s.commit()

    return {"terms": row, "privacy": row, "refund": row}


def record_legal_acceptance(
    *,
    session: Session,
    user: Any,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, LegalAcceptance]:
    user_id = getattr(user, "id", None)
    if user_id is None:
        raise LegalServiceError("User id is required")

    return record_full_acceptance_bundle(
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        session=session,
    )

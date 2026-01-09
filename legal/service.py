# legal/service.py
# Purpose: Legal versions + acceptance service layer (root-based imports)
# Fixes: IndentationError + removes any freightpay.* assumptions

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from db import db
from legal.models import LegalVersion, LegalAcceptance


class LegalServiceError(Exception):
    pass


def _session() -> Session:
    return db.session


def get_active_legal_version(*, doc_type: str, session: Optional[Session] = None) -> Optional[LegalVersion]:
    """
    Returns the latest ACTIVE legal version for a given doc_type (terms/privacy/refund).
    """
    s = session or _session()
    return (
        s.query(LegalVersion)
        .filter(LegalVersion.doc_type == doc_type, LegalVersion.is_active.is_(True))
        .order_by(desc(LegalVersion.version_number), desc(LegalVersion.created_at))
        .first()
    )


def get_required_versions(session: Optional[Session] = None) -> dict:
    """
    Returns required current versions for all doc types.
    """
    return {
        "terms": get_active_legal_version(doc_type="terms", session=session),
        "privacy": get_active_legal_version(doc_type="privacy", session=session),
        "refund": get_active_legal_version(doc_type="refund", session=session),
    }


def user_has_accepted_current(*, user_id: str, session: Optional[Session] = None) -> bool:
    """
    True only if the user has accepted the currently-active versions of terms/privacy/refund.
    """
    s = session or _session()
    required = get_required_versions(session=s)

    # If any required version is missing in DB, treat as NOT accepted (misconfigured)
    if not required["terms"] or not required["privacy"] or not required["refund"]:
        return False

    # Find latest acceptance for each doc_type
    for doc_type, version in required.items():
        accepted = (
            s.query(LegalAcceptance)
            .filter(
                LegalAcceptance.user_id == user_id,
                LegalAcceptance.doc_type == doc_type,
                LegalAcceptance.legal_version_id == version.id,
                LegalAcceptance.accepted.is_(True),
            )
            .first()
        )
        if not accepted:
            return False

    return True


def record_acceptance(
    *,
    user_id: str,
    doc_type: str,
    legal_version_id: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    accepted: bool = True,
    session: Optional[Session] = None,
) -> LegalAcceptance:
    """
    Creates an acceptance record. (Idempotency is handled by allowing duplicates; enforcement checks exact version.)
    """
    s = session or _session()

    lv = s.query(LegalVersion).filter(LegalVersion.id == legal_version_id).one_or_none()
    if not lv:
        raise LegalServiceError("Legal version not found")

    if lv.doc_type != doc_type:
        raise LegalServiceError("doc_type does not match legal_version")

    row = LegalAcceptance(
        user_id=user_id,
        doc_type=doc_type,
        legal_version_id=legal_version_id,
        accepted=bool(accepted),
        accepted_at=datetime.utcnow(),
        ip_address=ip_address,
        user_agent=user_agent,
    )

    s.add(row)
    s.commit()
    return row


def record_full_acceptance_bundle(
    *,
    user_id: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session: Optional[Session] = None,
) -> dict:
    """
    Records acceptance for the current active terms/privacy/refund versions in one call.
    """
    s = session or _session()
    required = get_required_versions(session=s)

    if not required["terms"] or not required["privacy"] or not required["refund"]:
        raise LegalServiceError("Missing required legal versions (seed not run or versions inactive)")

    out = {}
    out["terms"] = record_acceptance(
        user_id=user_id,
        doc_type="terms",
        legal_version_id=required["terms"].id,
        ip_address=ip_address,
        user_agent=user_agent,
        accepted=True,
        session=s,
    )
    out["privacy"] = record_acceptance(
        user_id=user_id,
        doc_type="privacy",
        legal_version_id=required["privacy"].id,
        ip_address=ip_address,
        user_agent=user_agent,
        accepted=True,
        session=s,
    )
    out["refund"] = record_acceptance(
        user_id=user_id,
        doc_type="refund",
        legal_version_id=required["refund"].id,
        ip_address=ip_address,
        user_agent=user_agent,
        accepted=True,
        session=s,
    )
    return out

# File: compliance/seed.py
# Purpose: Seed / update legal documents (Terms, Privacy, Refund)
# Status: Production-ready
# Date: 2026-01-26

from datetime import datetime

from db import db
from compliance.models import LegalDocument


def seed_legal_document(
    *,
    doc_key: str,
    version: str,
    effective_at: datetime | None = None,
):
    effective_at = effective_at or datetime.utcnow()

    existing = (
        LegalDocument.query
        .filter_by(doc_key=doc_key, version=version)
        .first()
    )

    if existing:
        return existing

    # Deactivate older versions
    LegalDocument.query.filter_by(
        doc_key=doc_key,
        is_active=True,
    ).update({"is_active": False})

    doc = LegalDocument(
        doc_key=doc_key,
        version=version,
        effective_at=effective_at,
        is_active=True,
    )

    db.session.add(doc)
    db.session.commit()

    return doc


def seed_all_legal():
    seed_legal_document(doc_key="terms", version="2026-01-26")
    seed_legal_document(doc_key="privacy", version="2026-01-26")
    seed_legal_document(doc_key="refund", version="2026-01-26")

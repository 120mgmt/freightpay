# File: compliance/terms.py
# Purpose: Legal acceptance helpers for Terms / Privacy
# Status: Enterprise hardened
# Date: 2026-03-05

from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import jsonify

from db import db
from compliance.models import LegalDocument, UserLegalAcceptance


def get_active_legal_versions(doc_keys: list[str] | None = None) -> dict[str, dict[str, Any]]:
    keys = doc_keys or ["terms", "privacy"]
    payload: dict[str, dict[str, Any]] = {}

    for key in keys:
        doc = (
            LegalDocument.query
            .filter_by(doc_key=key, is_active=True)
            .order_by(LegalDocument.effective_at.desc())
            .first()
        )
        payload[key] = {
            "doc_key": key,
            "version": doc.version if doc else None,
            "effective_at": doc.effective_at.isoformat() if doc and doc.effective_at else None,
            "checksum": doc.checksum if doc else None,
            "is_active": bool(doc),
        }

    return payload


def user_has_current_legal_acceptance(user_id: int, doc_keys: list[str] | None = None) -> bool:
    keys = doc_keys or ["terms", "privacy"]

    for key in keys:
        doc = (
            LegalDocument.query
            .filter_by(doc_key=key, is_active=True)
            .order_by(LegalDocument.effective_at.desc())
            .first()
        )
        if not doc:
            return False

        acceptance = (
            UserLegalAcceptance.query
            .filter_by(
                user_id=user_id,
                doc_key=key,
                version=doc.version,
                accepted=True,
            )
            .first()
        )
        if acceptance is None:
            return False

    return True


def accept_current_legal_documents(user_id: int, doc_keys: list[str] | None = None) -> list[dict[str, Any]]:
    keys = doc_keys or ["terms", "privacy"]
    accepted_items: list[dict[str, Any]] = []

    for key in keys:
        doc = (
            LegalDocument.query
            .filter_by(doc_key=key, is_active=True)
            .order_by(LegalDocument.effective_at.desc())
            .first()
        )
        if not doc:
            continue

        record = (
            UserLegalAcceptance.query
            .filter_by(user_id=user_id, doc_key=key, version=doc.version)
            .first()
        )

        if not record:
            record = UserLegalAcceptance(
                user_id=user_id,
                doc_key=key,
                version=doc.version,
                accepted=True,
                accepted_at=datetime.utcnow(),
            )
            db.session.add(record)
        else:
            record.accepted = True
            record.accepted_at = datetime.utcnow()

        accepted_items.append(
            {
                "doc_key": key,
                "version": doc.version,
                "accepted": True,
            }
        )

    if accepted_items:
        db.session.commit()

    return accepted_items


def legal_acceptance_error_response():
    return (
        jsonify(
            {
                "error": "legal_acceptance_required",
                "message": "You must accept the active Terms of Service and Privacy Policy.",
                "required_docs": ["terms", "privacy"],
            }
        ),
        403,
    )

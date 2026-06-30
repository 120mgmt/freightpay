# compliance/models.py
# Central compliance models: Terms/Privacy acceptance + versioning hooks

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Boolean, DateTime, UniqueConstraint, Index

from db import db  # LedgerHaul uses db.py (Flask-SQLAlchemy instance)


class LegalDocument(db.Model):
    __tablename__ = "legal_documents"

    id = Column(Integer, primary_key=True)
    doc_key = Column(String(64), nullable=False)          # e.g., "terms", "privacy"
    version = Column(String(64), nullable=False)          # e.g., "2026-01-25"
    checksum = Column(String(128), nullable=True)         # optional: sha256 of content
    effective_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("doc_key", "version", name="uq_legal_documents_key_version"),
        Index("ix_legal_documents_key_active", "doc_key", "is_active"),
    )


class UserLegalAcceptance(db.Model):
    __tablename__ = "user_legal_acceptances"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    doc_key = Column(String(64), nullable=False)          # "terms" | "privacy"
    version = Column(String(64), nullable=False)
    accepted = Column(Boolean, nullable=False, default=False)
    accepted_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "doc_key", "version", name="uq_user_legal_acceptance"),
        Index("ix_user_legal_user_doc", "user_id", "doc_key"),
    )

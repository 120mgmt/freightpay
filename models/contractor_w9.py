# File: models/contractor_w9.py
# Purpose: W-9 on file for a contractor — either an uploaded document or the
#          fillable form completed in-app. One row per contractor.

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import UniqueConstraint

from db import db

W9_METHODS = ("upload", "form")
TIN_TYPES = ("ssn", "ein")


class ContractorW9(db.Model):
    __tablename__ = "contractor_w9"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    contractor_id = db.Column(
        db.Integer,
        db.ForeignKey("contractors.id", ondelete="CASCADE"),
        nullable=False,
    )
    method = db.Column(db.String(16), nullable=False, default="form", server_default="form")

    # =========================
    # UPLOADED DOCUMENT
    # =========================
    # Bytes live in Postgres: the host has no persistent disk, so anything
    # written to the filesystem disappears on the next deploy.
    file_name = db.Column(db.String(255), nullable=True)
    file_mime = db.Column(db.String(100), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    file_bytes = db.Column(db.LargeBinary, nullable=True)
    file_sha256 = db.Column(db.String(64), nullable=True)
    uploaded_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # =========================
    # FILLABLE FORM
    # =========================
    form_name = db.Column(db.String(255), nullable=True)
    form_business_name = db.Column(db.String(255), nullable=True)
    form_tax_classification = db.Column(db.String(50), nullable=True)
    form_exempt_payee_code = db.Column(db.String(20), nullable=True)
    form_fatca_code = db.Column(db.String(20), nullable=True)
    form_address_line1 = db.Column(db.String(255), nullable=True)
    form_address_line2 = db.Column(db.String(255), nullable=True)
    form_city = db.Column(db.String(120), nullable=True)
    form_state = db.Column(db.String(50), nullable=True)
    form_postal_code = db.Column(db.String(20), nullable=True)
    form_requester = db.Column(db.String(255), nullable=True)
    form_account_numbers = db.Column(db.String(255), nullable=True)
    form_tin_type = db.Column(db.String(10), nullable=True)
    # Stored, but never serialized — only the last 4 leave the server.
    form_tin = db.Column(db.String(32), nullable=True)
    form_signature_name = db.Column(db.String(255), nullable=True)
    form_signed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    form_certified = db.Column(
        db.Boolean, nullable=False, default=False, server_default=db.text("false")
    )

    # =========================
    # AUDIT
    # =========================
    created_by_user_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("contractor_id", name="uq_contractor_w9_contractor"),
    )

    # =========================
    # SERIALIZATION
    # =========================
    @property
    def tin_last4(self) -> str | None:
        digits = "".join(ch for ch in (self.form_tin or "") if ch.isdigit())
        return digits[-4:] if len(digits) >= 4 else None

    def to_dict(self) -> dict[str, Any]:
        """
        Safe representation.

        Deliberately excludes file_bytes and form_tin — the document is served
        only by the download route, and the full TIN never leaves the server.
        """
        return {
            "contractor_id": self.contractor_id,
            "company_id": self.company_id,
            "method": self.method,
            "has_upload": bool(self.file_name),
            "has_form": bool(self.form_signed_at),
            "file": {
                "name": self.file_name,
                "mime": self.file_mime,
                "size": self.file_size,
                "sha256": self.file_sha256,
                "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            }
            if self.file_name
            else None,
            "form": {
                "name": self.form_name,
                "business_name": self.form_business_name,
                "tax_classification": self.form_tax_classification,
                "exempt_payee_code": self.form_exempt_payee_code,
                "fatca_code": self.form_fatca_code,
                "address_line1": self.form_address_line1,
                "address_line2": self.form_address_line2,
                "city": self.form_city,
                "state": self.form_state,
                "postal_code": self.form_postal_code,
                "requester": self.form_requester,
                "account_numbers": self.form_account_numbers,
                "tin_type": self.form_tin_type,
                "tin_last4": self.tin_last4,
                "signature_name": self.form_signature_name,
                "signed_at": self.form_signed_at.isoformat() if self.form_signed_at else None,
                "certified": bool(self.form_certified),
            }
            if self.form_signed_at
            else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


__all__ = ["ContractorW9", "W9_METHODS", "TIN_TYPES"]

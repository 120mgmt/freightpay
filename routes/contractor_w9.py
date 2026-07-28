# File: routes/contractor_w9.py
# Purpose: W-9 on file per contractor — upload an existing document, or fill the
#          form in digitally. Company-scoped with a strict tenant check.

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Optional

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required, verify_jwt_in_request
from sqlalchemy import select
from werkzeug.utils import secure_filename

from db import db
from models.contractor import Contractor
from models.contractor_w9 import TIN_TYPES, ContractorW9

contractor_w9_bp = Blueprint("contractor_w9", __name__, url_prefix="/api/contractors")

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB — a W-9 scan is far smaller

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

# Magic bytes, so the stored file really is what the extension claims.
_MAGIC = (
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)

TAX_CLASSES = {
    "individual",
    "sole_prop",
    "llc",
    "partnership",
    "s_corp",
    "c_corp",
    "nonprofit",
    "other",
}


def _json_error(message: str, status: int = 400, code: str = "BAD_REQUEST"):
    return jsonify({"error": code, "message": message}), status


def _require_auth():
    """JWT + company scope. Rejects an X-Company-Id that disagrees with the token."""
    verify_jwt_in_request()
    identity = get_jwt_identity()
    if not identity or not isinstance(identity, dict):
        return None, _json_error("Authentication required", 401, "UNAUTHORIZED")

    company_id = identity.get("company_id")
    user_id = identity.get("user_id") or identity.get("id")

    header_company_id = request.headers.get("X-Company-Id")
    if header_company_id:
        try:
            header_company_id = int(str(header_company_id).strip())
        except (TypeError, ValueError):
            return None, _json_error("Invalid X-Company-Id header", 400, "INVALID_COMPANY_ID")
        if company_id is not None and int(company_id) != header_company_id:
            return None, _json_error("Company scope mismatch", 403, "FORBIDDEN")
        company_id = header_company_id

    try:
        company_id = int(company_id)
    except (TypeError, ValueError):
        return None, _json_error("Company context is required", 403, "FORBIDDEN")

    return {"company_id": company_id, "user_id": user_id}, None


def _load_contractor(company_id: int, contractor_id: int) -> Optional[Contractor]:
    return db.session.execute(
        select(Contractor).where(
            Contractor.id == contractor_id,
            Contractor.company_id == company_id,
            Contractor.deleted_at.is_(None),
        )
    ).scalar_one_or_none()


def _get_or_create_w9(company_id: int, contractor_id: int, user_id: Any) -> ContractorW9:
    record = db.session.execute(
        select(ContractorW9).where(ContractorW9.contractor_id == contractor_id)
    ).scalar_one_or_none()
    if record is None:
        record = ContractorW9(
            company_id=company_id,
            contractor_id=contractor_id,
            created_by_user_id=user_id if isinstance(user_id, int) else None,
        )
        db.session.add(record)
    return record


def _mark_received(contractor: Contractor) -> None:
    contractor.w9_received = True
    contractor.w9_received_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if contractor.onboarding_status == "pending_w9":
        contractor.onboarding_status = "ready"


def _sniff_mime(head: bytes) -> Optional[str]:
    for prefix, mime in _MAGIC:
        if head.startswith(prefix):
            return mime
    return None


@contractor_w9_bp.get("/<int:contractor_id>/w9")
@jwt_required()
def get_w9(contractor_id: int):
    """W-9 metadata. Never returns the document bytes or the full TIN."""
    auth, err = _require_auth()
    if err:
        return err

    contractor = _load_contractor(auth["company_id"], contractor_id)
    if not contractor:
        return _json_error("Contractor not found", 404, "NOT_FOUND")

    record = db.session.execute(
        select(ContractorW9).where(ContractorW9.contractor_id == contractor_id)
    ).scalar_one_or_none()

    if not record:
        return jsonify(
            {
                "contractor_id": contractor_id,
                "has_upload": False,
                "has_form": False,
                "w9_received": bool(contractor.w9_received),
            }
        ), 200

    payload = record.to_dict()
    payload["w9_received"] = bool(contractor.w9_received)
    return jsonify(payload), 200


@contractor_w9_bp.post("/<int:contractor_id>/w9/upload")
@jwt_required()
def upload_w9(contractor_id: int):
    """Store an existing W-9 document (PDF or image) against the contractor."""
    auth, err = _require_auth()
    if err:
        return err

    contractor = _load_contractor(auth["company_id"], contractor_id)
    if not contractor:
        return _json_error("Contractor not found", 404, "NOT_FOUND")

    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return _json_error("No file provided", 400, "FILE_REQUIRED")

    filename = secure_filename(upload.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return _json_error(
            f"Unsupported file type '.{ext}'. Upload a PDF, PNG or JPG.",
            400,
            "UNSUPPORTED_FILE_TYPE",
        )

    # Read with one byte of headroom so an oversize file is detected, not truncated.
    blob = upload.read(MAX_UPLOAD_BYTES + 1)
    if not blob:
        return _json_error("The uploaded file is empty", 400, "EMPTY_FILE")
    if len(blob) > MAX_UPLOAD_BYTES:
        return _json_error(
            f"File is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
            413,
            "FILE_TOO_LARGE",
        )

    sniffed = _sniff_mime(blob[:16])
    if sniffed is None:
        return _json_error(
            "That file does not look like a PDF or image.", 400, "UNSUPPORTED_FILE_TYPE"
        )

    record = _get_or_create_w9(auth["company_id"], contractor_id, auth["user_id"])
    record.method = "upload"
    record.file_name = filename
    record.file_mime = sniffed
    record.file_size = len(blob)
    record.file_bytes = blob
    record.file_sha256 = hashlib.sha256(blob).hexdigest()
    record.uploaded_at = datetime.now(timezone.utc)

    _mark_received(contractor)

    try:
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return _json_error(f"Could not save the W-9: {exc}", 500, "SAVE_FAILED")

    return jsonify(record.to_dict()), 201


@contractor_w9_bp.get("/<int:contractor_id>/w9/file")
@jwt_required()
def download_w9(contractor_id: int):
    """Stream the stored document. The only route that returns the bytes."""
    auth, err = _require_auth()
    if err:
        return err

    if not _load_contractor(auth["company_id"], contractor_id):
        return _json_error("Contractor not found", 404, "NOT_FOUND")

    record = db.session.execute(
        select(ContractorW9).where(ContractorW9.contractor_id == contractor_id)
    ).scalar_one_or_none()
    if not record or not record.file_bytes:
        return _json_error("No W-9 document on file", 404, "NOT_FOUND")

    return Response(
        record.file_bytes,
        mimetype=record.file_mime or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{record.file_name or "w9"}"',
            "Content-Length": str(record.file_size or len(record.file_bytes)),
        },
    )


@contractor_w9_bp.post("/<int:contractor_id>/w9/form")
@jwt_required()
def submit_w9_form(contractor_id: int):
    """Record a digitally completed W-9 (structured fields + typed signature)."""
    auth, err = _require_auth()
    if err:
        return err

    contractor = _load_contractor(auth["company_id"], contractor_id)
    if not contractor:
        return _json_error("Contractor not found", 404, "NOT_FOUND")

    data = request.get_json(silent=True) or {}

    def _s(key: str) -> Optional[str]:
        value = data.get(key)
        if value is None:
            return None
        return str(value).strip() or None

    name = _s("name")
    if not name:
        return _json_error("Name is required (line 1 of the W-9)", 400, "NAME_REQUIRED")

    tax_classification = (_s("tax_classification") or "").lower()
    if tax_classification not in TAX_CLASSES:
        return _json_error(
            "Select a federal tax classification", 400, "INVALID_TAX_CLASSIFICATION"
        )

    tin_type = (_s("tin_type") or "").lower()
    if tin_type not in TIN_TYPES:
        return _json_error("Choose whether the TIN is an SSN or an EIN", 400, "INVALID_TIN_TYPE")

    tin_digits = "".join(ch for ch in (_s("tin") or "") if ch.isdigit())
    if len(tin_digits) != 9:
        return _json_error(
            "Enter the full 9-digit SSN or EIN", 400, "INVALID_TIN"
        )

    signature_name = _s("signature_name")
    if not signature_name:
        return _json_error("Type your name to sign the form", 400, "SIGNATURE_REQUIRED")

    if not bool(data.get("certified")):
        return _json_error(
            "You must certify the W-9 statements before submitting", 400, "CERTIFICATION_REQUIRED"
        )

    address_line1 = _s("address_line1")
    city = _s("city")
    state = _s("state")
    postal_code = _s("postal_code")
    if not (address_line1 and city and state and postal_code):
        return _json_error("A complete address is required", 400, "ADDRESS_REQUIRED")

    record = _get_or_create_w9(auth["company_id"], contractor_id, auth["user_id"])
    record.method = "form"
    record.form_name = name
    record.form_business_name = _s("business_name")
    record.form_tax_classification = tax_classification
    record.form_exempt_payee_code = _s("exempt_payee_code")
    record.form_fatca_code = _s("fatca_code")
    record.form_address_line1 = address_line1
    record.form_address_line2 = _s("address_line2")
    record.form_city = city
    record.form_state = state
    record.form_postal_code = postal_code
    record.form_requester = _s("requester")
    record.form_account_numbers = _s("account_numbers")
    record.form_tin_type = tin_type
    record.form_tin = tin_digits
    record.form_signature_name = signature_name
    record.form_signed_at = datetime.now(timezone.utc)
    record.form_certified = True

    # Mirror the last 4 onto the contractor; the full TIN stays in this table.
    contractor.tin_last4 = tin_digits[-4:]
    _mark_received(contractor)

    try:
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return _json_error(f"Could not save the W-9: {exc}", 500, "SAVE_FAILED")

    return jsonify(record.to_dict()), 201


@contractor_w9_bp.delete("/<int:contractor_id>/w9")
@jwt_required()
def delete_w9(contractor_id: int):
    auth, err = _require_auth()
    if err:
        return err

    contractor = _load_contractor(auth["company_id"], contractor_id)
    if not contractor:
        return _json_error("Contractor not found", 404, "NOT_FOUND")

    record = db.session.execute(
        select(ContractorW9).where(ContractorW9.contractor_id == contractor_id)
    ).scalar_one_or_none()
    if not record:
        return _json_error("No W-9 on file", 404, "NOT_FOUND")

    contractor.w9_received = False
    contractor.w9_received_at = None

    try:
        db.session.delete(record)
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return _json_error(f"Could not remove the W-9: {exc}", 500, "DELETE_FAILED")

    return jsonify({"status": "deleted", "contractor_id": contractor_id}), 200

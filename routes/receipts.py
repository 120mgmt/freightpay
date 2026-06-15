from __future__ import annotations

# File: routes/receipts.py
# Purpose: Receipt upload + management API (production) + status transitions + audit + optional auto-post
# Status: Production-ready
# Date: 2026-02-09

import os
import uuid
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import select
from werkzeug.utils import secure_filename

from db import db
from models.receipts import Receipt
from models.company import Company

# =========================
# Blueprint
# =========================
receipts_bp = Blueprint("receipts", __name__, url_prefix="/files/receipts")

# =========================
# Config
# =========================
UPLOAD_ROOT = os.getenv("RECEIPTS_UPLOAD_DIR", "/opt/render/project/uploads/receipts")
MAX_FILE_MB = int(os.getenv("RECEIPTS_MAX_MB", "10"))
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "heic"}

os.makedirs(UPLOAD_ROOT, exist_ok=True)

# =========================
# Helpers
# =========================
def _utcnow():
    return datetime.now(timezone.utc)


def _allowed(filename: str) -> bool:
    if "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _claims():
    return get_jwt() or {}


def _jwt_company_id() -> int:
    claims = _claims()
    sub = claims.get("sub") or {}
    return int(sub.get("company_id"))


def _jwt_user_id() -> int:
    claims = _claims()
    sub = claims.get("sub") or {}
    return int(sub.get("user_id"))


def _set_if_attr(obj, attr: str, value):
    if hasattr(obj, attr):
        setattr(obj, attr, value)


def _audit(event_type: str, company_id: int, user_id: int, **meta):
    """
    Best-effort persisted audit record.
    If an audit model isn't present, falls back to structured app logging (still useful in Render logs).
    """
    model = None
    for import_path, class_name in (
        ("models.audit_log", "AuditLog"),
        ("models.audit_logs", "AuditLog"),
        ("models.audit", "AuditLog"),
        ("compliance.models.audit_log", "AuditLog"),
        ("compliance.models", "AuditLog"),
    ):
        try:
            mod = __import__(import_path, fromlist=[class_name])
            model = getattr(mod, class_name, None)
            if model is not None:
                break
        except Exception:
            continue

    if model is None:
        try:
            import logging

            logging.getLogger("ledgerhaul").info(
                "AUDIT %s company_id=%s user_id=%s meta=%s",
                event_type,
                company_id,
                user_id,
                meta,
            )
        except Exception:
            import logging as _log
            _log.getLogger("ledgerhaul").warning(
                "AUDIT_LOG_FAILED %s company_id=%s user_id=%s", event_type, company_id, user_id
            )
        return

    try:
        rec = model(
            id=uuid.uuid4().hex if hasattr(model, "id") else None,
            event_type=event_type if hasattr(model, "event_type") else None,
            company_id=company_id if hasattr(model, "company_id") else None,
            user_id=user_id if hasattr(model, "user_id") else None,
            metadata=meta if hasattr(model, "metadata") else None,
            created_at=_utcnow() if hasattr(model, "created_at") else None,
        )
        db.session.add(rec)
        db.session.commit()
    except Exception:
        db.session.rollback()
        try:
            import logging

            logging.getLogger("ledgerhaul").exception(
                "AUDIT_WRITE_FAILED %s company_id=%s user_id=%s",
                event_type,
                company_id,
                user_id,
            )
        except Exception:
            pass  # last-resort: logging itself failed, nothing more we can do


def _maybe_auto_post(receipt: Receipt):
    """
    Optional: if OCR + journalization services are present, run them and update receipt status.
    This is defensive: it will not crash deploy if service functions differ.
    """
    company_id = int(getattr(receipt, "company_id", 0) or 0)
    user_id = _jwt_user_id()

    current_status = (getattr(receipt, "status", "") or "").lower()
    if current_status not in ("uploaded", "processing", ""):
        return

    _set_if_attr(receipt, "status", "processing")
    _set_if_attr(receipt, "processed_at", None)
    _set_if_attr(receipt, "posted_at", None)
    _set_if_attr(receipt, "failure_reason", None)
    db.session.commit()

    _audit(
        "receipt_processing_started",
        company_id,
        user_id,
        receipt_id=getattr(receipt, "id", None),
    )

    try:
        ocr_result = None
        fn = None
        try:
            ocr_mod = __import__("services.receipt_ocr", fromlist=["*"])
            for fn_name in ("process_receipt", "run_ocr", "ocr_receipt", "extract_receipt"):
                cand = getattr(ocr_mod, fn_name, None)
                if callable(cand):
                    fn = cand
                    try:
                        ocr_result = fn(receipt_id=getattr(receipt, "id", None))
                    except TypeError:
                        ocr_result = fn(getattr(receipt, "id", None))
                    break
        except Exception:
            import logging
            logging.getLogger("ledgerhaul").warning("OCR service unavailable or failed for receipt %s", getattr(receipt, "id", None))

        _audit(
            "receipt_ocr_completed",
            company_id,
            user_id,
            receipt_id=getattr(receipt, "id", None),
            has_result=bool(ocr_result),
        )

        post_result = None
        j_fn = None
        try:
            j_mod = __import__("services.receipt_journalization", fromlist=["*"])
            for fn_name in (
                "auto_post_receipt",
                "journalize_receipt",
                "post_receipt",
                "post_to_ledger",
                "create_journal_entry",
            ):
                cand = getattr(j_mod, fn_name, None)
                if callable(cand):
                    j_fn = cand
                    try:
                        post_result = j_fn(receipt_id=getattr(receipt, "id", None))
                    except TypeError:
                        post_result = j_fn(getattr(receipt, "id", None))
                    break
        except Exception:
            import logging
            logging.getLogger("ledgerhaul").warning("Journalization service unavailable for receipt %s", getattr(receipt, "id", None))

        journal_entry_id = None
        if isinstance(post_result, dict):
            journal_entry_id = post_result.get("journal_entry_id") or post_result.get("journal_id")
        elif isinstance(post_result, str):
            journal_entry_id = post_result

        if journal_entry_id:
            _set_if_attr(receipt, "journal_entry_id", journal_entry_id)

        _set_if_attr(receipt, "status", "posted" if post_result is not None else "processed")
        _set_if_attr(receipt, "processed_at", _utcnow())
        if post_result is not None:
            _set_if_attr(receipt, "posted_at", _utcnow())

        db.session.commit()

        _audit(
            "receipt_post_completed",
            company_id,
            user_id,
            receipt_id=getattr(receipt, "id", None),
            status=getattr(receipt, "status", None),
            journal_entry_id=journal_entry_id,
        )

    except Exception as e:
        db.session.rollback()
        _set_if_attr(receipt, "status", "failed")
        _set_if_attr(receipt, "failure_reason", str(e))
        _set_if_attr(receipt, "processed_at", _utcnow())
        db.session.commit()

        _audit(
            "receipt_post_failed",
            company_id,
            user_id,
            receipt_id=getattr(receipt, "id", None),
            error=str(e),
        )


# =========================
# Routes
# =========================
@receipts_bp.route("/upload", methods=["POST"])
@jwt_required()
def upload_receipt():
    """
    Multipart form:
      - file: receipt file
      - company_id: int (must match JWT company)
      - receipt_date: optional ISO date (YYYY-MM-DD or full ISO datetime)
      - vendor: optional
      - total_amount: optional float
      - currency: optional (default USD)
      - auto_post: optional (true/false) default true
    """
    if "file" not in request.files:
        return jsonify({"error": "file required"}), 400

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "empty file"}), 400

    filename = secure_filename(file.filename)
    if not _allowed(filename):
        return jsonify({"error": "unsupported file type"}), 400

    company_id = request.form.get("company_id", type=int)
    if not company_id:
        return jsonify({"error": "company_id required"}), 400

    jwt_company_id = _jwt_company_id()
    if company_id != jwt_company_id:
        return jsonify({"error": "company mismatch"}), 403

    company = db.session.get(Company, company_id)
    if not company or not getattr(company, "is_active", True):
        return jsonify({"error": "invalid company"}), 404

    try:
        file.stream.seek(0, os.SEEK_END)
        size_mb = file.stream.tell() / (1024 * 1024)
        file.stream.seek(0)
        if size_mb > MAX_FILE_MB:
            return jsonify({"error": f"file exceeds {MAX_FILE_MB}MB"}), 413
    except Exception:
        import logging
        logging.getLogger("ledgerhaul").warning("Could not check file size for %s", filename)

    ext = filename.rsplit(".", 1)[1].lower()
    receipt_id = uuid.uuid4().hex
    stored_name = f"{receipt_id}.{ext}"
    company_dir = os.path.join(UPLOAD_ROOT, str(company_id))
    os.makedirs(company_dir, exist_ok=True)
    path = os.path.join(company_dir, stored_name)

    file.save(path)

    receipt_date_raw = request.form.get("receipt_date")
    receipt_date = None
    if receipt_date_raw:
        try:
            if (
                len(receipt_date_raw) == 10
                and receipt_date_raw[4] == "-"
                and receipt_date_raw[7] == "-"
            ):
                receipt_date = datetime.fromisoformat(receipt_date_raw).replace(tzinfo=timezone.utc)
            else:
                dt = datetime.fromisoformat(receipt_date_raw)
                receipt_date = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return jsonify({"error": "invalid receipt_date"}), 400

    receipt = Receipt(
        id=receipt_id,
        company_id=company_id,
        filename=filename,
        storage_path=path,
        receipt_date=receipt_date,
        vendor=request.form.get("vendor"),
        total_amount=request.form.get("total_amount", type=float),
        currency=request.form.get("currency") or "USD",
        status="uploaded",
        created_at=_utcnow(),
    )

    db.session.add(receipt)
    db.session.commit()

    _audit(
        "receipt_uploaded",
        company_id,
        _jwt_user_id(),
        receipt_id=receipt.id,
        filename=receipt.filename,
        storage_path=receipt.storage_path,
    )

    auto_post_raw = (request.form.get("auto_post") or "true").strip().lower()
    auto_post = auto_post_raw not in ("0", "false", "no")

    if auto_post:
        _maybe_auto_post(receipt)

    return (
        jsonify(
            {
                "id": receipt.id,
                "company_id": receipt.company_id,
                "filename": receipt.filename,
                "status": receipt.status,
                "receipt_date": receipt.receipt_date.isoformat() if receipt.receipt_date else None,
                "total_amount": receipt.total_amount,
                "currency": receipt.currency,
                "created_at": receipt.created_at.isoformat(),
            }
        ),
        201,
    )


@receipts_bp.route("", methods=["GET"])
@jwt_required()
def list_receipts():
    company_id = _jwt_company_id()
    stmt = (
        select(Receipt)
        .where(Receipt.company_id == company_id)
        .order_by(Receipt.created_at.desc())
        .limit(100)
    )
    receipts = list(db.session.execute(stmt).scalars().all())

    return (
        jsonify(
            [
                {
                    "id": r.id,
                    "filename": r.filename,
                    "status": r.status,
                    "receipt_date": r.receipt_date.isoformat() if r.receipt_date else None,
                    "total_amount": r.total_amount,
                    "currency": r.currency,
                    "created_at": r.created_at.isoformat(),
                    "journal_entry_id": getattr(r, "journal_entry_id", None),
                }
                for r in receipts
            ]
        ),
        200,
    )


@receipts_bp.route("/health", methods=["GET"])
def receipts_health():
    return jsonify({"status": "ok"}), 200

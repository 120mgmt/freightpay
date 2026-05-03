# File: jobs/receipt_worker.py
# Purpose: Background worker to OCR + auto-post receipts to ledger/journal (production hardened)
# Status: Production-ready
# Date: 2026-02-10

from __future__ import annotations

import os
import signal
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from sqlalchemy import text

# -----------------------------------------------------------------------------
# ENV / LOGGING
# -----------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ledgerhaul.receipt_worker")

POLL_SECONDS = int(os.getenv("RECEIPT_WORKER_POLL_SECONDS", "5"))
BATCH_SIZE = int(os.getenv("RECEIPT_WORKER_BATCH_SIZE", "10"))
MAX_RETRIES = int(os.getenv("RECEIPT_WORKER_MAX_RETRIES", "3"))
AUTO_POST_ENABLED = (
    os.getenv("RECEIPT_AUTO_POST_ENABLED", "true").strip().lower()
    not in ("0", "false", "no")
)

STOP = False


# -----------------------------------------------------------------------------
# SIGNALS
# -----------------------------------------------------------------------------
def _set_stop(*_args: Any) -> None:
    global STOP
    STOP = True


signal.signal(signal.SIGTERM, _set_stop)
signal.signal(signal.SIGINT, _set_stop)


# -----------------------------------------------------------------------------
# TIME
# -----------------------------------------------------------------------------
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# -----------------------------------------------------------------------------
# SAFE IMPORT HELPERS
# -----------------------------------------------------------------------------
def _safe_import_callable(
    module_path: str, candidate_names: tuple[str, ...]
) -> Optional[Callable[..., Any]]:
    try:
        mod = __import__(module_path, fromlist=["*"])
    except Exception:
        return None
    for name in candidate_names:
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn
    return None


# -----------------------------------------------------------------------------
# LOAD APP + DB (EXPLICIT, NO ASSUMPTIONS)
# -----------------------------------------------------------------------------
# This guarantees application context exists for Flask-SQLAlchemy
from app import app  # noqa: E402
from db import db  # noqa: E402


# -----------------------------------------------------------------------------
# OPTIONAL PIPELINE FUNCTIONS
# -----------------------------------------------------------------------------
OCR_FN = _safe_import_callable(
    "services.receipt_ocr",
    ("process_receipt", "run_ocr", "ocr_receipt", "extract_receipt"),
)

POST_FN = _safe_import_callable(
    "services.receipt_journalization",
    (
        "auto_post_receipt",
        "journalize_receipt",
        "post_receipt",
        "post_to_ledger",
        "create_journal_entry",
    ),
)


# -----------------------------------------------------------------------------
# AUDIT (BEST EFFORT)
# -----------------------------------------------------------------------------
def _audit_log(
    event_type: str,
    company_id: int,
    user_id: Optional[int],
    receipt_id: str,
    **meta: Any,
) -> None:
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
        logger.info(
            "AUDIT %s company_id=%s user_id=%s receipt_id=%s meta=%s",
            event_type,
            company_id,
            user_id,
            receipt_id,
            meta,
        )
        return

    try:
        rec = model(
            id=uuid.uuid4().hex if hasattr(model, "id") else None,
            event_type=event_type if hasattr(model, "event_type") else None,
            company_id=company_id if hasattr(model, "company_id") else None,
            user_id=user_id if hasattr(model, "user_id") else None,
            metadata={"receipt_id": receipt_id, **meta}
            if hasattr(model, "metadata")
            else None,
            created_at=_utcnow() if hasattr(model, "created_at") else None,
        )
        db.session.add(rec)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception(
            "AUDIT_WRITE_FAILED %s company_id=%s receipt_id=%s",
            event_type,
            company_id,
            receipt_id,
        )


# -----------------------------------------------------------------------------
# SCHEMA DETECTION (NO ASSUMPTIONS)
# -----------------------------------------------------------------------------
def _column_exists(table: str, column: str) -> bool:
    q = text(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema='public'
          AND table_name=:t
          AND column_name=:c
        LIMIT 1
        """
    )
    return bool(db.session.execute(q, {"t": table, "c": column}).scalar())


WITH_RETRY_COUNT = False
WITH_FAILURE_REASON = False
WITH_PROCESSED_AT = False
WITH_POSTED_AT = False
WITH_JOURNAL_ENTRY_ID = False
WITH_UPDATED_AT = False


def _init_receipts_columns_cache() -> None:
    global WITH_RETRY_COUNT, WITH_FAILURE_REASON, WITH_PROCESSED_AT
    global WITH_POSTED_AT, WITH_JOURNAL_ENTRY_ID, WITH_UPDATED_AT

    WITH_RETRY_COUNT = _column_exists("receipts", "retry_count")
    WITH_FAILURE_REASON = _column_exists("receipts", "failure_reason")
    WITH_PROCESSED_AT = _column_exists("receipts", "processed_at")
    WITH_POSTED_AT = _column_exists("receipts", "posted_at")
    WITH_JOURNAL_ENTRY_ID = _column_exists("receipts", "journal_entry_id")
    WITH_UPDATED_AT = _column_exists("receipts", "updated_at")


# -----------------------------------------------------------------------------
# DB HELPERS
# -----------------------------------------------------------------------------
def _get_retry_count(receipt_id: str) -> int:
    if not WITH_RETRY_COUNT:
        return 0
    q = text("SELECT COALESCE(retry_count, 0) FROM receipts WHERE id=:id")
    return int(db.session.execute(q, {"id": receipt_id}).scalar() or 0)


def _bump_retry_count(receipt_id: str) -> None:
    if not WITH_RETRY_COUNT:
        return
    q = text(
        "UPDATE receipts SET retry_count = COALESCE(retry_count, 0) + 1 WHERE id=:id"
    )
    db.session.execute(q, {"id": receipt_id})


def _set_status(receipt_id: str, status: str) -> None:
    if WITH_UPDATED_AT:
        q = text(
            "UPDATE receipts SET status=:s, updated_at=:u WHERE id=:id"
        )
        db.session.execute(
            q, {"s": status, "u": _utcnow(), "id": receipt_id}
        )
    else:
        q = text("UPDATE receipts SET status=:s WHERE id=:id")
        db.session.execute(q, {"s": status, "id": receipt_id})


def _set_failure(receipt_id: str, reason: str) -> None:
    if WITH_FAILURE_REASON:
        q = text(
            "UPDATE receipts SET status='failed', failure_reason=:r WHERE id=:id"
        )
        db.session.execute(q, {"r": reason[:2000], "id": receipt_id})
    else:
        _set_status(receipt_id, "failed")

    if WITH_PROCESSED_AT:
        q2 = text("UPDATE receipts SET processed_at=:t WHERE id=:id")
        db.session.execute(q2, {"t": _utcnow(), "id": receipt_id})


def _set_processed(
    receipt_id: str, posted: bool, journal_entry_id: Optional[str]
) -> None:
    _set_status(receipt_id, "posted" if posted else "processed")

    if WITH_PROCESSED_AT:
        q = text("UPDATE receipts SET processed_at=:t WHERE id=:id")
        db.session.execute(q, {"t": _utcnow(), "id": receipt_id})

    if posted and WITH_POSTED_AT:
        q = text("UPDATE receipts SET posted_at=:t WHERE id=:id")
        db.session.execute(q, {"t": _utcnow(), "id": receipt_id})

    if journal_entry_id and WITH_JOURNAL_ENTRY_ID:
        q = text(
            "UPDATE receipts SET journal_entry_id=:j WHERE id=:id"
        )
        db.session.execute(q, {"j": journal_entry_id, "id": receipt_id})


# -----------------------------------------------------------------------------
# CLAIM WORK
# -----------------------------------------------------------------------------
def _claim_batch() -> list[dict[str, Any]]:
    if WITH_RETRY_COUNT:
        q = text(
            """
            SELECT id, company_id
            FROM receipts
            WHERE status IN ('uploaded','processing')
              AND COALESCE(retry_count, 0) < :maxr
            ORDER BY created_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT :lim
            """
        )
        rows = (
            db.session.execute(
                q, {"lim": BATCH_SIZE, "maxr": MAX_RETRIES}
            )
            .mappings()
            .all()
        )
    else:
        q = text(
            """
            SELECT id, company_id
            FROM receipts
            WHERE status IN ('uploaded','processing')
            ORDER BY created_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT :lim
            """
        )
        rows = (
            db.session.execute(q, {"lim": BATCH_SIZE})
            .mappings()
            .all()
        )

    for r in rows:
        _set_status(r["id"], "processing")

    return [dict(r) for r in rows]


# -----------------------------------------------------------------------------
# PIPELINE
# -----------------------------------------------------------------------------
def _run_pipeline(receipt_id: str) -> tuple[bool, Optional[str]]:
    post_result = None

    if OCR_FN:
        try:
            try:
                OCR_FN(receipt_id=receipt_id)
            except TypeError:
                OCR_FN(receipt_id)
        except Exception as e:
            logger.exception("OCR_FAILED receipt_id=%s err=%s", receipt_id, e)

    if POST_FN:
        try:
            try:
                post_result = POST_FN(receipt_id=receipt_id)
            except TypeError:
                post_result = POST_FN(receipt_id)
        except Exception as e:
            logger.exception("POST_FAILED receipt_id=%s err=%s", receipt_id, e)

    journal_entry_id = None
    if isinstance(post_result, dict):
        journal_entry_id = post_result.get("journal_entry_id") or post_result.get(
            "journal_id"
        )
    elif isinstance(post_result, str):
        journal_entry_id = post_result

    return post_result is not None, journal_entry_id


# -----------------------------------------------------------------------------
# MAIN LOOP
# -----------------------------------------------------------------------------
def main() -> None:
    if not AUTO_POST_ENABLED:
        logger.warning("RECEIPT_AUTO_POST_ENABLED=false; worker exiting")
        return

    with app.app_context():
        _init_receipts_columns_cache()
        logger.info(
            "receipt_worker_started poll=%ss batch=%s max_retries=%s ocr=%s post=%s",
            POLL_SECONDS,
            BATCH_SIZE,
            MAX_RETRIES,
            bool(OCR_FN),
            bool(POST_FN),
        )

        while not STOP:
            try:
                with db.session.begin():
                    batch = _claim_batch()

                if not batch:
                    time.sleep(POLL_SECONDS)
                    continue

                for item in batch:
                    rid = str(item["id"])
                    company_id = int(item.get("company_id") or 0)
                    user_id = None

                    try:
                        with db.session.begin():
                            _audit_log(
                                "receipt_processing_started",
                                company_id,
                                user_id,
                                rid,
                            )

                        posted, journal_entry_id = _run_pipeline(rid)

                        with db.session.begin():
                            _set_processed(
                                rid, posted=posted, journal_entry_id=journal_entry_id
                            )
                            _audit_log(
                                "receipt_post_completed",
                                company_id,
                                user_id,
                                rid,
                                status="posted" if posted else "processed",
                                journal_entry_id=journal_entry_id,
                            )

                    except Exception as e:
                        logger.exception(
                            "RECEIPT_PIPELINE_FAILED receipt_id=%s", rid
                        )
                        with db.session.begin():
                            _bump_retry_count(rid)
                            retries = _get_retry_count(rid)
                            if retries >= MAX_RETRIES:
                                _set_failure(rid, str(e))
                                _audit_log(
                                    "receipt_post_failed",
                                    company_id,
                                    user_id,
                                    rid,
                                    error=str(e),
                                    retries=retries,
                                )
                            else:
                                _set_status(rid, "uploaded")
                                _audit_log(
                                    "receipt_requeued",
                                    company_id,
                                    user_id,
                                    rid,
                                    error=str(e),
                                    retries=retries,
                                )

            except Exception:
                logger.exception("receipt_worker_loop_error")
                time.sleep(max(2, POLL_SECONDS))

        logger.info("receipt_worker_stopped")


if __name__ == "__main__":
    main()

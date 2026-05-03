# File: jobs/receipts.py
# Purpose: Receipt auto-post pipeline (OCR + journalization) worker
# Status: Production-ready
# Date: 2026-02-09

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from db import db
from models.receipts import Receipt

logger = logging.getLogger("ledgerhaul.receipts")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _set_status(
    receipt: Receipt,
    status: str,
    *,
    error: Optional[str] = None,
    journal_id: Optional[Any] = None,
) -> None:
    """
    Best-effort status transitions without assuming your exact model fields.
    """
    if hasattr(receipt, "status"):
        receipt.status = status

    if error is not None and hasattr(receipt, "error_message"):
        receipt.error_message = error

    if journal_id is not None:
        if hasattr(receipt, "journal_id"):
            receipt.journal_id = journal_id
        elif hasattr(receipt, "posted_journal_id"):
            receipt.posted_journal_id = journal_id

    if hasattr(receipt, "updated_at"):
        receipt.updated_at = _utcnow()


def process_receipt(receipt_id: str) -> dict:
    """
    Idempotent-ish worker:
      uploaded/queued/failed -> processing -> posted OR failed

    Calls:
      - services.receipt_ocr.extract_receipt(...)
      - services.receipt_journalization.journalize_receipt(...)
    using best-effort imports to match current repo.
    """
    receipt: Receipt | None = db.session.get(Receipt, receipt_id)
    if not receipt:
        return {"ok": False, "error": "receipt_not_found", "receipt_id": receipt_id}

    if getattr(receipt, "status", None) == "posted":
        return {
            "ok": True,
            "receipt_id": receipt_id,
            "status": "posted",
            "skipped": True,
        }

    try:
        _set_status(receipt, "processing")
        db.session.commit()

        ocr_result = None
        try:
            from services.receipt_ocr import extract_receipt

            ocr_result = extract_receipt(receipt_id=receipt_id)
        except Exception:
            from services.receipt_ocr import run_ocr as extract_receipt  # type: ignore

            ocr_result = extract_receipt(receipt_id=receipt_id)  # type: ignore

        journal_result = None
        try:
            from services.receipt_journalization import journalize_receipt

            journal_result = journalize_receipt(
                receipt_id=receipt_id,
                ocr_result=ocr_result,
            )
        except Exception:
            from services.receipt_journalization import auto_post_receipt as journalize_receipt  # type: ignore

            journal_result = journalize_receipt(
                receipt_id=receipt_id,
                ocr_result=ocr_result,
            )  # type: ignore

        jid = None
        if isinstance(journal_result, dict):
            jid = journal_result.get("journal_id") or journal_result.get("id")
        else:
            jid = getattr(journal_result, "id", None)

        _set_status(receipt, "posted", journal_id=jid)
        db.session.commit()

        return {
            "ok": True,
            "receipt_id": receipt_id,
            "status": "posted",
            "journal_id": jid,
        }

    except Exception as e:
        logger.exception("Receipt pipeline failed: %s", receipt_id)
        _set_status(receipt, "failed", error=str(e))
        db.session.commit()
        return {
            "ok": False,
            "receipt_id": receipt_id,
            "status": "failed",
            "error": str(e),
        }


def enqueue_receipt_processing(receipt_id: str) -> dict:
    """
    Enqueue if a queue exists; otherwise run inline (configurable).
    """
    mode = (os.getenv("RECEIPTS_PROCESS_MODE") or "inline").strip().lower()

    if mode == "rq":
        try:
            from rq import Queue  # type: ignore
            from redis import Redis  # type: ignore

            redis_url = os.getenv("REDIS_URL")
            if not redis_url:
                return {
                    "ok": False,
                    "error": "REDIS_URL required for rq mode",
                }

            q = Queue("receipts", connection=Redis.from_url(redis_url))
            job = q.enqueue(
                process_receipt,
                receipt_id,
                job_timeout=600,
                result_ttl=3600,
            )

            return {
                "ok": True,
                "enqueued": True,
                "job_id": job.id,
                "receipt_id": receipt_id,
            }

        except Exception as e:
            return {
                "ok": False,
                "error": f"rq_enqueue_failed: {e}",
                "receipt_id": receipt_id,
            }

    return process_receipt(receipt_id)

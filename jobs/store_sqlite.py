# File: jobs/store_sqlite.py
# Purpose: Production-safe SQLite store for:
#   1) Webhook idempotency (Stripe event_id tracking)
#   2) Background jobs (retries, exports, payouts, etc.)
#
# Notes:
# - Uses SQLite with WAL mode. Works on Render, but you MUST mount a persistent disk
#   and set JOBS_DB_PATH to that disk path for true production durability.
# - Default DB path is /tmp (ephemeral) if JOBS_DB_PATH is not set.

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

DEFAULT_DB_PATH = os.getenv("JOBS_DB_PATH", "/tmp/jobs.db")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DEFAULT_DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    # WAL helps with concurrency in web + worker processes
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    conn = _db()
    try:
        # Stripe / webhook idempotency store
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS webhook_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                livemode INTEGER NOT NULL DEFAULT 0,
                received_at TEXT NOT NULL,
                processed_at TEXT,
                status TEXT NOT NULL DEFAULT 'received', -- received|processed|failed
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_webhook_events_status ON webhook_events(status)"
        )

        # Generic background job queue
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,                 -- e.g. 'stripe_webhook', 'export_csv', 'payout_run'
                status TEXT NOT NULL DEFAULT 'queued', -- queued|running|succeeded|failed|dead
                priority INTEGER NOT NULL DEFAULT 100, -- lower number = higher priority
                run_after_epoch INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 10,
                last_error TEXT,
                payload_json TEXT NOT NULL,
                idempotency_key TEXT,               -- optional unique key to prevent duplicates
                UNIQUE(kind, idempotency_key)       -- only enforced when idempotency_key is non-null
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_queue ON jobs(status, run_after_epoch, priority)"
        )
        conn.commit()
    finally:
        conn.close()


# ---------- Webhook idempotency ----------

@dataclass(frozen=True)
class WebhookUpsertResult:
    should_process: bool
    status: str  # received|processed|failed
    attempts: int


def record_webhook_event(
    *,
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
    livemode: bool = False,
) -> WebhookUpsertResult:
    """
    Insert the event if new. If already exists, decide whether to process again.
    Returns should_process=True only if:
      - new event inserted, OR
      - existing event is failed and may be retried (status=failed)
    """
    init_db()

    conn = _db()
    try:
        row = conn.execute(
            "SELECT event_id, status, attempts FROM webhook_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()

        if row:
            status = str(row["status"])
            attempts = int(row["attempts"])
            # Only retry if previously failed
            return WebhookUpsertResult(
                should_process=(status == "failed"),
                status=status,
                attempts=attempts,
            )

        conn.execute(
            """
            INSERT INTO webhook_events (event_id, event_type, livemode, received_at, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event_id,
                event_type,
                1 if livemode else 0,
                _utc_now_iso(),
                json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
            ),
        )
        conn.commit()
        return WebhookUpsertResult(should_process=True, status="received", attempts=0)
    finally:
        conn.close()


def mark_webhook_attempt(event_id: str) -> None:
    init_db()
    conn = _db()
    try:
        conn.execute(
            """
            UPDATE webhook_events
            SET attempts = attempts + 1,
                status = CASE WHEN status = 'processed' THEN status ELSE 'received' END
            WHERE event_id = ?
            """,
            (event_id,),
        )
        conn.commit()
    finally:
        conn.close()


def mark_webhook_processed(event_id: str) -> None:
    init_db()
    conn = _db()
    try:
        conn.execute(
            """
            UPDATE webhook_events
            SET status='processed',
                processed_at=?,
                last_error=NULL
            WHERE event_id = ?
            """,
            (_utc_now_iso(), event_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_webhook_failed(event_id: str, error: str) -> None:
    init_db()
    conn = _db()
    try:
        conn.execute(
            """
            UPDATE webhook_events
            SET status='failed',
                last_error=?,
                processed_at=NULL
            WHERE event_id = ?
            """,
            (error[:2000], event_id),
        )
        conn.commit()
    finally:
        conn.close()


# ---------- Background jobs queue ----------

def enqueue_job(
    *,
    kind: str,
    payload: Dict[str, Any],
    run_after_seconds: int = 0,
    priority: int = 100,
    max_attempts: int = 10,
    idempotency_key: Optional[str] = None,
) -> str:
    """
    Creates a queued job. If idempotency_key is provided, duplicates will be rejected
    (same kind + same idempotency_key).
    Returns job_id for the created job, or the existing job_id if duplicate.
    """
    init_db()

    job_id = str(uuid.uuid4())
    now_iso = _utc_now_iso()
    run_after_epoch = int(time.time()) + max(0, int(run_after_seconds))

    conn = _db()
    try:
        if idempotency_key:
            existing = conn.execute(
                """
                SELECT job_id FROM jobs
                WHERE kind = ? AND idempotency_key = ?
                """,
                (kind, idempotency_key),
            ).fetchone()
            if existing:
                return str(existing["job_id"])

        conn.execute(
            """
            INSERT INTO jobs (
                job_id, kind, status, priority, run_after_epoch,
                created_at, updated_at, max_attempts, payload_json, idempotency_key
            )
            VALUES (?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                kind,
                int(priority),
                int(run_after_epoch),
                now_iso,
                now_iso,
                int(max_attempts),
                json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
                idempotency_key,
            ),
        )
        conn.commit()
        return job_id
    finally:
        conn.close()


def claim_next_job(*, kinds: Optional[Tuple[str, ...]] = None) -> Optional[Dict[str, Any]]:
    """
    Atomically claims the next runnable job (status=queued and run_after_epoch <= now).
    Returns a dict with job info, or None if none available.
    """
    init_db()
    now_epoch = int(time.time())
    now_iso = _utc_now_iso()

    conn = _db()
    try:
        conn.execute("BEGIN IMMEDIATE;")  # lock for safe claim

        where = "status = 'queued' AND run_after_epoch <= ?"
        params: list[Any] = [now_epoch]

        if kinds:
            placeholders = ",".join(["?"] * len(kinds))
            where += f" AND kind IN ({placeholders})"
            params.extend(list(kinds))

        row = conn.execute(
            f"""
            SELECT job_id, kind, priority, run_after_epoch, attempts, max_attempts, payload_json
            FROM jobs
            WHERE {where}
            ORDER BY priority ASC, run_after_epoch ASC, created_at ASC
            LIMIT 1
            """,
            tuple(params),
        ).fetchone()

        if not row:
            conn.execute("COMMIT;")
            return None

        job_id = str(row["job_id"])
        conn.execute(
            """
            UPDATE jobs
            SET status='running',
                started_at=COALESCE(started_at, ?),
                updated_at=?,
                attempts=attempts+1
            WHERE job_id=? AND status='queued'
            """,
            (now_iso, now_iso, job_id),
        )
        conn.execute("COMMIT;")

        payload = json.loads(row["payload_json"])
        return {
            "job_id": job_id,
            "kind": str(row["kind"]),
            "priority": int(row["priority"]),
            "attempts": int(row["attempts"]) + 1,
            "max_attempts": int(row["max_attempts"]),
            "payload": payload if isinstance(payload, dict) else {"_payload": payload},
        }
    except Exception:
        try:
            conn.execute("ROLLBACK;")
        except Exception:
            pass
        raise
    finally:
        conn.close()


def complete_job(job_id: str) -> None:
    init_db()
    now_iso = _utc_now_iso()
    conn = _db()
    try:
        conn.execute(
            """
            UPDATE jobs
            SET status='succeeded',
                finished_at=?,
                updated_at=?,
                last_error=NULL
            WHERE job_id=?
            """,
            (now_iso, now_iso, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def fail_job(job_id: str, error: str, *, retry_in_seconds: int = 30) -> None:
    """
    Marks job failed. If attempts < max_attempts, re-queues with backoff.
    Otherwise moves to 'dead'.
    """
    init_db()
    now_iso = _utc_now_iso()
    now_epoch = int(time.time())
    conn = _db()
    try:
        row = conn.execute(
            "SELECT attempts, max_attempts FROM jobs WHERE job_id=?",
            (job_id,),
        ).fetchone()
        if not row:
            return

        attempts = int(row["attempts"])
        max_attempts = int(row["max_attempts"])

        if attempts >= max_attempts:
            conn.execute(
                """
                UPDATE jobs
                SET status='dead',
                    finished_at=?,
                    updated_at=?,
                    last_error=?
                WHERE job_id=?
                """,
                (now_iso, now_iso, error[:2000], job_id),
            )
        else:
            run_after_epoch = now_epoch + max(5, int(retry_in_seconds))
            conn.execute(
                """
                UPDATE jobs
                SET status='queued',
                    updated_at=?,
                    last_error=?,
                    run_after_epoch=?
                WHERE job_id=?
                """,
                (now_iso, error[:2000], int(run_after_epoch), job_id),
            )

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    eid = "evt_test_" + uuid.uuid4().hex
    r = record_webhook_event(event_id=eid, event_type="test.event", payload={"id": eid}, livemode=False)
    assert r.should_process is True
    r2 = record_webhook_event(event_id=eid, event_type="test.event", payload={"id": eid}, livemode=False)
    assert r2.should_process is False

    jid = enqueue_job(kind="test_job", payload={"hello": "world"}, idempotency_key="k1")
    jid2 = enqueue_job(kind="test_job", payload={"hello": "world"}, idempotency_key="k1")
    assert jid == jid2
    print("jobs/store_sqlite.py OK")

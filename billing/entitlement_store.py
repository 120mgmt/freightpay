# File: billing/entitlement_store.py
# Purpose: Persist and retrieve customer subscription + entitlement state (FULL deployment hardened).
# Used by:
#   - billing.webhooks (_apply_entitlements_update)
#   - billing.subscription_gate (fast-path lookup)
#
# Storage: SQLite default (Render-safe). Can swap to Postgres later without API changes.
# FULL DEPLOYMENT FIXES INCLUDED:
#   - Creates parent directory for DB if needed
#   - WAL mode + busy_timeout for concurrent writes (gunicorn workers)
#   - Idempotent init
#   - Stores Stripe subscription_id + current_period_end + price_ids JSON (base + per-employee)
#   - Backwards compatible with prior columns (price_id still present)
#   - Safe JSON handling

from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

DB_PATH = os.getenv("ENTITLEMENT_DB_PATH", "/tmp/entitlements.db")


def _ensure_db_dir() -> None:
    try:
        d = os.path.dirname(DB_PATH)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
    except Exception:
        # If directory cannot be created, sqlite will fail later with a clear error.
        pass


def _conn() -> sqlite3.Connection:
    _ensure_db_dir()
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row

    # Concurrency safety for multi-worker gunicorn
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA foreign_keys=ON;")
    except Exception:
        pass

    return conn


def _init() -> None:
    with _conn() as c:
        # Backwards compatible: keep price_id + add price_ids_json and other useful fields.
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS customer_subscriptions (
                customer_id TEXT PRIMARY KEY,
                active INTEGER NOT NULL,
                status TEXT,
                subscription_id TEXT,
                price_id TEXT,
                price_ids_json TEXT,
                current_period_end INTEGER,
                entitlements_json TEXT,
                updated_at INTEGER NOT NULL
            )
            """
        )
        # Helpful indexes for lookup/ops
        c.execute("CREATE INDEX IF NOT EXISTS idx_customer_subscriptions_updated_at ON customer_subscriptions(updated_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_customer_subscriptions_subscription_id ON customer_subscriptions(subscription_id)")
        c.commit()


_init()


def upsert_customer_subscription(
    *,
    customer_id: str,
    active: bool,
    status: Optional[str] = None,
    subscription_id: Optional[str] = None,
    price_id: Optional[str] = None,
    price_ids: Optional[List[str]] = None,
    current_period_end: Optional[int] = None,
    entitlements: Optional[Dict[str, Any]] = None,
    updated_at: Optional[int] = None,
) -> None:
    """
    Insert or update the latest known subscription state for a customer.
    Called from Stripe webhooks.

    Supports full Stripe deployments:
      - subscription_id
      - price_ids (list; base + per-employee add-ons)
      - current_period_end (epoch seconds)
      - entitlements (dict)
    """
    if not customer_id:
        raise ValueError("customer_id is required")

    ts = int(updated_at or time.time())

    ent_payload = json.dumps(entitlements) if entitlements is not None else None
    price_ids_payload = json.dumps(price_ids) if price_ids is not None else None

    with _conn() as c:
        c.execute(
            """
            INSERT INTO customer_subscriptions
                (customer_id, active, status, subscription_id, price_id, price_ids_json, current_period_end, entitlements_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(customer_id) DO UPDATE SET
                active = excluded.active,
                status = excluded.status,
                subscription_id = excluded.subscription_id,
                price_id = excluded.price_id,
                price_ids_json = excluded.price_ids_json,
                current_period_end = excluded.current_period_end,
                entitlements_json = excluded.entitlements_json,
                updated_at = excluded.updated_at
            """,
            (
                customer_id,
                1 if active else 0,
                status,
                subscription_id,
                price_id,
                price_ids_payload,
                current_period_end,
                ent_payload,
                ts,
            ),
        )
        c.commit()


def get_customer_subscription(customer_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached subscription + entitlement state.
    Used by subscription_gate as a fast-path.
    """
    if not customer_id:
        return None

    with _conn() as c:
        row = c.execute(
            """
            SELECT customer_id, active, status, subscription_id, price_id, price_ids_json, current_period_end, entitlements_json, updated_at
            FROM customer_subscriptions
            WHERE customer_id = ?
            """,
            (customer_id,),
        ).fetchone()

    if not row:
        return None

    ent = None
    if row["entitlements_json"]:
        try:
            ent = json.loads(row["entitlements_json"])
        except Exception:
            ent = None

    price_ids = None
    if row["price_ids_json"]:
        try:
            v = json.loads(row["price_ids_json"])
            price_ids = v if isinstance(v, list) else None
        except Exception:
            price_ids = None

    return {
        "customer_id": row["customer_id"],
        "active": bool(row["active"]),
        "status": row["status"],
        "subscription_id": row["subscription_id"],
        "price_id": row["price_id"],               # backward compatible single primary price
        "price_ids": price_ids,                    # full list of price_ids (base + per-employee)
        "current_period_end": row["current_period_end"],
        "entitlements": ent,
        "updated_at": row["updated_at"],
    }


def delete_customer_subscription(customer_id: str) -> None:
    """
    Hard delete (rare; typically only for data purges).
    """
    if not customer_id:
        return

    with _conn() as c:
        c.execute("DELETE FROM customer_subscriptions WHERE customer_id = ?", (customer_id,))
        c.commit()


def purge_stale_subscriptions(*, older_than_seconds: int) -> int:
    """
    Optional maintenance helper: deletes rows not updated recently.
    Returns count deleted.
    """
    cutoff = int(time.time()) - int(older_than_seconds)
    with _conn() as c:
        cur = c.execute("DELETE FROM customer_subscriptions WHERE updated_at < ?", (cutoff,))
        c.commit()
        return int(cur.rowcount or 0)


if __name__ == "__main__":
    now = int(time.time())
    upsert_customer_subscription(
        customer_id="cus_test",
        active=True,
        status="active",
        subscription_id="sub_test",
        price_id="price_base_test",
        price_ids=["price_base_test", "price_per_employee_test"],
        current_period_end=now + 30 * 24 * 3600,
        entitlements={"plan": "starter", "features": {"payroll_run": True}, "limits": {"drivers": 10}},
        updated_at=now,
    )
    rec = get_customer_subscription("cus_test")
    assert rec and rec["active"] is True
    assert rec["subscription_id"] == "sub_test"
    assert rec["price_id"] == "price_base_test"
    assert isinstance(rec.get("price_ids"), (list, type(None)))
    delete_customer_subscription("cus_test")
    assert get_customer_subscription("cus_test") is None
    print("billing/entitlement_store.py FULL DEPLOYMENT OK")

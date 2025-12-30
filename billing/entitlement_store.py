# File: billing/entitlement_store.py
# Purpose: Persist and retrieve customer subscription + entitlement state.
# Used by:
#   - billing.webhooks (_apply_entitlements_update)
#   - billing.subscription_gate (optional fast-path lookup)
#
# Production-ready, no placeholders.
# Storage: SQLite (safe default on Render; replace with Postgres later without API changes)

from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any, Dict, Optional

DB_PATH = os.getenv("ENTITLEMENT_DB_PATH", "/tmp/entitlements.db")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init() -> None:
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS customer_subscriptions (
                customer_id TEXT PRIMARY KEY,
                active INTEGER NOT NULL,
                status TEXT,
                price_id TEXT,
                entitlements_json TEXT,
                updated_at INTEGER NOT NULL
            )
            """
        )
        c.commit()


_init()


def upsert_customer_subscription(
    *,
    customer_id: str,
    active: bool,
    status: Optional[str],
    price_id: Optional[str],
    entitlements: Optional[Dict[str, Any]],
    updated_at: Optional[int] = None,
) -> None:
    """
    Insert or update the latest known subscription state for a customer.
    Called from Stripe webhooks.
    """
    ts = int(updated_at or time.time())
    payload = json.dumps(entitlements) if entitlements is not None else None

    with _conn() as c:
        c.execute(
            """
            INSERT INTO customer_subscriptions
                (customer_id, active, status, price_id, entitlements_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(customer_id) DO UPDATE SET
                active = excluded.active,
                status = excluded.status,
                price_id = excluded.price_id,
                entitlements_json = excluded.entitlements_json,
                updated_at = excluded.updated_at
            """,
            (
                customer_id,
                1 if active else 0,
                status,
                price_id,
                payload,
                ts,
            ),
        )
        c.commit()


def get_customer_subscription(customer_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached subscription + entitlement state.
    Used by subscription_gate as an optional fast-path.
    """
    with _conn() as c:
        row = c.execute(
            """
            SELECT customer_id, active, status, price_id, entitlements_json, updated_at
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

    return {
        "customer_id": row["customer_id"],
        "active": bool(row["active"]),
        "status": row["status"],
        "price_id": row["price_id"],
        "entitlements": ent,
        "updated_at": row["updated_at"],
    }


def delete_customer_subscription(customer_id: str) -> None:
    """
    Hard delete (rare; typically only for data purges).
    """
    with _conn() as c:
        c.execute(
            "DELETE FROM customer_subscriptions WHERE customer_id = ?",
            (customer_id,),
        )
        c.commit()


if __name__ == "__main__":
    # Sanity checks
    upsert_customer_subscription(
        customer_id="cus_test",
        active=True,
        status="active",
        price_id="price_test",
        entitlements={"plan": "starter", "features": {"payroll_run": True}, "limits": {}},
        updated_at=int(time.time()),
    )
    rec = get_customer_subscription("cus_test")
    assert rec and rec["active"] is True
    delete_customer_subscription("cus_test")
    assert get_customer_subscription("cus_test") is None
    print("billing/entitlement_store.py OK")

# File: billing/entitlement_store.py
# Purpose: Persist and retrieve customer subscription + entitlement state (FULL production).
# Used by:
#   - billing.webhooks (_apply_entitlements)
#   - billing.subscription_gate (fast-path lookup / cache)
#
# Storage: PRIMARY DATABASE (Postgres on Render) — NOT /tmp SQLite (ephemeral).
#
# Date: 2026-01-24
# Status: Production-grade (durable persistence, idempotent upserts, safe JSON handling)

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from db import db


def _now() -> int:
    return int(time.time())


# The table (customer_id PK, active, status, subscription_id, price_id,
# price_ids_json, current_period_end, entitlements_json, updated_at) is
# created by migrations/versions/20260419_customer_subscriptions.py. It used
# to self-create here via a raw "CREATE TABLE IF NOT EXISTS" run at module
# IMPORT time — before any Flask app context exists, so db.engine access
# raised "working outside of application context" and the bare except
# swallowed it. The table was never created: every webhook-driven entitlement
# upsert and every subscription_gate.py cache lookup silently failed.


def record_stripe_event_id(event_id: str, *, received_at: Optional[int] = None) -> bool:
    """
    Back-compat helper. Webhook idempotency is now handled in billing/webhooks.py
    (stripe_webhook_events table). This remains for any callers that still use it.

    Returns True if treated as "new"; False if already exists.
    """
    eid = (event_id or "").strip()
    if not eid:
        return True

    ts = int(received_at or _now())
    try:
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO stripe_webhook_events (event_id, received_at)
                    VALUES (:event_id, :received_at)
                    ON CONFLICT (event_id) DO NOTHING
                    """
                ),
                {"event_id": eid, "received_at": ts},
            )
        # Determine if it exists (cheap check)
        with db.engine.begin() as conn:
            row = conn.execute(
                text("SELECT event_id FROM stripe_webhook_events WHERE event_id = :event_id"),
                {"event_id": eid},
            ).fetchone()
        return bool(row)
    except Exception:
        # If idempotency store fails, do not block webhook processing
        return True


def purge_stripe_events(*, older_than_seconds: int) -> int:
    cutoff = _now() - int(older_than_seconds)
    try:
        with db.engine.begin() as conn:
            res = conn.execute(
                text("DELETE FROM stripe_webhook_events WHERE received_at < :cutoff"),
                {"cutoff": cutoff},
            )
        return int(getattr(res, "rowcount", 0) or 0)
    except Exception:
        return 0


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

    Supports:
      - subscription_id
      - price_ids (list; base + per-employee add-ons)
      - current_period_end (epoch seconds)
      - entitlements (dict)
    """
    cid = (customer_id or "").strip()
    if not cid:
        raise ValueError("customer_id is required")

    ts = int(updated_at or _now())

    ent_payload = json.dumps(entitlements) if entitlements is not None else None
    price_ids_payload = json.dumps(price_ids) if price_ids is not None else None

    sql = """
    INSERT INTO customer_subscriptions
        (customer_id, active, status, subscription_id, price_id, price_ids_json,
         current_period_end, entitlements_json, updated_at)
    VALUES
        (:customer_id, :active, :status, :subscription_id, :price_id, :price_ids_json,
         :current_period_end, :entitlements_json, :updated_at)
    ON CONFLICT (customer_id) DO UPDATE SET
        active = EXCLUDED.active,
        status = EXCLUDED.status,
        subscription_id = EXCLUDED.subscription_id,
        price_id = EXCLUDED.price_id,
        price_ids_json = EXCLUDED.price_ids_json,
        current_period_end = EXCLUDED.current_period_end,
        entitlements_json = EXCLUDED.entitlements_json,
        updated_at = EXCLUDED.updated_at
    """

    with db.engine.begin() as conn:
        conn.execute(
            text(sql),
            {
                "customer_id": cid,
                "active": bool(active),
                "status": status,
                "subscription_id": subscription_id,
                "price_id": price_id,
                "price_ids_json": price_ids_payload,
                "current_period_end": current_period_end,
                "entitlements_json": ent_payload,
                "updated_at": ts,
            },
        )


def get_customer_subscription(customer_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached subscription + entitlement state.
    Used by subscription_gate as a fast-path.
    """
    cid = (customer_id or "").strip()
    if not cid:
        return None

    try:
        with db.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT customer_id, active, status, subscription_id, price_id, price_ids_json,
                           current_period_end, entitlements_json, updated_at
                    FROM customer_subscriptions
                    WHERE customer_id = :customer_id
                    """
                ),
                {"customer_id": cid},
            ).mappings().fetchone()

        if not row:
            return None

        ent = None
        if row.get("entitlements_json"):
            try:
                ent = json.loads(row["entitlements_json"])
            except Exception:
                ent = None

        price_ids = None
        if row.get("price_ids_json"):
            try:
                v = json.loads(row["price_ids_json"])
                price_ids = v if isinstance(v, list) else None
            except Exception:
                price_ids = None

        return {
            "customer_id": row["customer_id"],
            "active": bool(row["active"]),
            "status": row.get("status"),
            "subscription_id": row.get("subscription_id"),
            "price_id": row.get("price_id"),  # backward compatible single primary price
            "price_ids": price_ids,  # full list of price_ids (base + per-employee)
            "current_period_end": row.get("current_period_end"),
            "entitlements": ent,
            "updated_at": row.get("updated_at"),
        }
    except Exception:
        return None


def delete_customer_subscription(customer_id: str) -> None:
    """
    Hard delete (rare; typically only for data purges).
    """
    cid = (customer_id or "").strip()
    if not cid:
        return

    with db.engine.begin() as conn:
        conn.execute(
            text("DELETE FROM customer_subscriptions WHERE customer_id = :customer_id"),
            {"customer_id": cid},
        )


def purge_stale_subscriptions(*, older_than_seconds: int) -> int:
    """
    Optional maintenance helper: deletes rows not updated recently.
    Returns count deleted.
    """
    cutoff = _now() - int(older_than_seconds)
    try:
        with db.engine.begin() as conn:
            res = conn.execute(
                text("DELETE FROM customer_subscriptions WHERE updated_at < :cutoff"),
                {"cutoff": cutoff},
            )
        return int(getattr(res, "rowcount", 0) or 0)
    except Exception:
        return 0


__all__ = [
    "upsert_customer_subscription",
    "get_customer_subscription",
    "delete_customer_subscription",
    "purge_stale_subscriptions",
    "record_stripe_event_id",
    "purge_stripe_events",
]


if __name__ == "__main__":
    now = _now()
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

    assert record_stripe_event_id("evt_test_1") is True
    purge_stripe_events(older_than_seconds=0)

    print("billing/entitlement_store.py FULL PRODUCTION OK")

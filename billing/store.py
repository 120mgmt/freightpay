from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


DB_PATH = os.getenv("BILLING_DB_PATH", os.getenv("DATABASE_PATH", "/tmp/app.db"))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_billing_db() -> None:
    conn = _db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stripe_customers (
                company_id TEXT PRIMARY KEY,
                stripe_customer_id TEXT NOT NULL,
                email TEXT,
                meta_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                company_id TEXT PRIMARY KEY,
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                status TEXT NOT NULL,
                cancel_at_period_end INTEGER DEFAULT 0,
                current_period_end INTEGER,
                price_id TEXT,
                plan_code TEXT,
                latest_invoice_id TEXT,
                meta_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def upsert_customer(company_id: str, stripe_customer_id: str, email: str = "", meta: Optional[Dict[str, Any]] = None) -> None:
    meta = meta or {}
    now = _utc_now_iso()
    conn = _db()
    try:
        conn.execute(
            """
            INSERT INTO stripe_customers (company_id, stripe_customer_id, email, meta_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_id) DO UPDATE SET
              stripe_customer_id=excluded.stripe_customer_id,
              email=excluded.email,
              meta_json=excluded.meta_json,
              updated_at=excluded.updated_at
            """,
            (company_id, stripe_customer_id, email, json.dumps(meta), now, now),
        )
        conn.commit()
    finally:
        conn.close()


def get_customer(company_id: str) -> Optional[Dict[str, Any]]:
    conn = _db()
    try:
        row = conn.execute(
            "SELECT company_id, stripe_customer_id, email, meta_json, created_at, updated_at FROM stripe_customers WHERE company_id = ?",
            (company_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["meta"] = json.loads(d.get("meta_json") or "{}")
        except Exception:
            d["meta"] = {}
        d.pop("meta_json", None)
        return d
    finally:
        conn.close()


def upsert_subscription(
    *,
    company_id: str,
    status: str,
    stripe_customer_id: str = "",
    stripe_subscription_id: str = "",
    cancel_at_period_end: bool = False,
    current_period_end: Optional[int] = None,
    price_id: str = "",
    plan_code: str = "",
    latest_invoice_id: str = "",
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    meta = meta or {}
    now = _utc_now_iso()
    conn = _db()
    try:
        conn.execute(
            """
            INSERT INTO subscriptions (
                company_id, stripe_customer_id, stripe_subscription_id, status, cancel_at_period_end,
                current_period_end, price_id, plan_code, latest_invoice_id, meta_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_id) DO UPDATE SET
              stripe_customer_id=excluded.stripe_customer_id,
              stripe_subscription_id=excluded.stripe_subscription_id,
              status=excluded.status,
              cancel_at_period_end=excluded.cancel_at_period_end,
              current_period_end=excluded.current_period_end,
              price_id=excluded.price_id,
              plan_code=excluded.plan_code,
              latest_invoice_id=excluded.latest_invoice_id,
              meta_json=excluded.meta_json,
              updated_at=excluded.updated_at
            """,
            (
                company_id,
                stripe_customer_id,
                stripe_subscription_id,
                status,
                1 if cancel_at_period_end else 0,
                current_period_end,
                price_id,
                plan_code,
                latest_invoice_id,
                json.dumps(meta),
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_subscription(company_id: str) -> Optional[Dict[str, Any]]:
    conn = _db()
    try:
        row = conn.execute(
            """
            SELECT company_id, stripe_customer_id, stripe_subscription_id, status, cancel_at_period_end,
                   current_period_end, price_id, plan_code, latest_invoice_id, meta_json, created_at, updated_at
            FROM subscriptions
            WHERE company_id = ?
            """,
            (company_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["meta"] = json.loads(d.get("meta_json") or "{}")
        except Exception:
            d["meta"] = {}
        d.pop("meta_json", None)
        d["cancel_at_period_end"] = bool(d.get("cancel_at_period_end"))
        return d
    finally:
        conn.close()


def is_subscription_active(company_id: str) -> Tuple[bool, str]:
    sub = get_subscription(company_id)
    if not sub:
        return False, "missing_subscription"
    status = (sub.get("status") or "").strip().lower()
    if status in {"active", "trialing"}:
        return True, status
    return False, status or "inactive"

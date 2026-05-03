# File: billing/usage_metering.py
# Purpose: Production-grade usage metering + plan limit enforcement (drivers, team, payroll runs, loads)
# Import targets:
#   - from billing.usage_metering import (
#         get_company_usage_month,
#         set_company_usage_metric,
#         increment_company_usage,
#         enforce_usage_limit,
#     )
# Date: 2026-01-26
# Status: FULL PRODUCTION (durable DB storage, deterministic month bucketing UTC, entitlement-based limits)

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar, cast

from flask import jsonify, request
from sqlalchemy import text

from db import db
from billing.customers import get_company_customer, get_or_create_company_customer
from billing.entitlement import Entitlements, entitlements_from_dict, entitlements_from_stripe_price_id
from billing.entitlement_store import get_customer_subscription

F = TypeVar("F", bound=Callable[..., Any])

# -----------------------------
# DB INIT (DURABLE)
# -----------------------------
def _now() -> int:
    return int(time.time())


def _ym_utc(ts: Optional[int] = None) -> str:
    dt = datetime.fromtimestamp(ts or _now(), tz=timezone.utc)
    return f"{dt.year:04d}-{dt.month:02d}"


def _init() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS company_usage_monthly (
        company_id INTEGER NOT NULL,
        year_month TEXT NOT NULL,
        drivers INTEGER NOT NULL DEFAULT 0,
        team_members INTEGER NOT NULL DEFAULT 0,
        payroll_runs INTEGER NOT NULL DEFAULT 0,
        loads INTEGER NOT NULL DEFAULT 0,
        updated_at BIGINT NOT NULL,
        PRIMARY KEY (company_id, year_month)
    );
    CREATE INDEX IF NOT EXISTS idx_company_usage_monthly_updated_at
        ON company_usage_monthly(updated_at);
    """
    try:
        with db.engine.begin() as conn:
            for stmt in [s.strip() for s in ddl.split(";") if s.strip()]:
                conn.execute(text(stmt))
    except Exception:
        # Do not crash import; callers will surface issues via API responses/logs
        pass


_init()

# -----------------------------
# METRICS
# -----------------------------
_ALLOWED_METRICS = {
    "drivers": "drivers",
    "team_members": "team_members",
    "payroll_runs_per_month": "payroll_runs",  # entitlement key -> db column
    "payroll_runs": "payroll_runs",
    "loads_per_month": "loads",                # entitlement key -> db column
    "loads": "loads",
}


def _metric_to_col(metric: str) -> Optional[str]:
    m = (metric or "").strip()
    if not m:
        return None
    return _ALLOWED_METRICS.get(m)


def _extract_company_id() -> Optional[int]:
    # Priority: header -> query -> JSON
    cid = request.headers.get("X-Company-Id")
    if isinstance(cid, str) and cid.strip():
        try:
            v = int(cid.strip())
            return v if v >= 0 else None
        except Exception:
            return None

    cid = request.args.get("company_id")
    if isinstance(cid, str) and cid.strip():
        try:
            v = int(cid.strip())
            return v if v >= 0 else None
        except Exception:
            return None

    data = request.get_json(silent=True) or {}
    if isinstance(data, dict):
        cid2 = data.get("company_id")
        if isinstance(cid2, (str, int)) and str(cid2).strip():
            try:
                v = int(str(cid2).strip())
                return v if v >= 0 else None
            except Exception:
                return None

    return None


def _resolve_stripe_customer_id(company_id: int) -> Optional[str]:
    """
    Production rule:
      - Prefer persisted mapping (billing/customers)
      - Recover/create if missing (stable behavior)
    """
    rec = get_company_customer(company_id)
    if rec and isinstance(rec.get("stripe_customer_id"), str):
        scid = rec["stripe_customer_id"].strip()
        return scid if scid.startswith("cus_") else None

    rec2 = get_or_create_company_customer(company_id=company_id)
    scid2 = (rec2.get("stripe_customer_id") or "").strip()
    return scid2 if scid2.startswith("cus_") else None


def _get_entitlements_for_company(company_id: int) -> Entitlements:
    """
    Uses durable webhook cache first:
      customer_subscriptions.entitlements_json / price_id
    Fallback:
      derive entitlements from price_id (starter default).
    """
    customer_id = _resolve_stripe_customer_id(company_id)
    if customer_id:
        rec = get_customer_subscription(customer_id)
        if rec:
            ent = entitlements_from_dict(rec.get("entitlements"))
            if ent is not None:
                return ent

            price_id = rec.get("price_id")
            return entitlements_from_stripe_price_id(price_id)

    # Deterministic fallback
    return entitlements_from_stripe_price_id(None)

# -----------------------------
# STORE / READ
# -----------------------------
def get_company_usage_month(*, company_id: int, year_month: Optional[str] = None) -> Dict[str, Any]:
    ym = (year_month or _ym_utc()).strip()
    with db.engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT company_id, year_month, drivers, team_members, payroll_runs, loads, updated_at
                FROM company_usage_monthly
                WHERE company_id = :company_id AND year_month = :year_month
                """
            ),
            {"company_id": int(company_id), "year_month": ym},
        ).mappings().fetchone()

        if not row:
            # return deterministic "empty" without forcing an insert
            return {
                "company_id": int(company_id),
                "year_month": ym,
                "drivers": 0,
                "team_members": 0,
                "payroll_runs": 0,
                "loads": 0,
                "updated_at": None,
            }

        return {
            "company_id": int(row["company_id"]),
            "year_month": row["year_month"],
            "drivers": int(row["drivers"] or 0),
            "team_members": int(row["team_members"] or 0),
            "payroll_runs": int(row["payroll_runs"] or 0),
            "loads": int(row["loads"] or 0),
            "updated_at": int(row["updated_at"]) if row.get("updated_at") is not None else None,
        }


def set_company_usage_metric(
    *,
    company_id: int,
    metric: str,
    value: int,
    year_month: Optional[str] = None,
) -> Dict[str, Any]:
    col = _metric_to_col(metric)
    if not col:
        raise ValueError("Invalid metric")

    ym = (year_month or _ym_utc()).strip()
    v = int(value)
    if v < 0:
        v = 0

    sql = f"""
    INSERT INTO company_usage_monthly (company_id, year_month, {col}, updated_at)
    VALUES (:company_id, :year_month, :val, :updated_at)
    ON CONFLICT (company_id, year_month) DO UPDATE SET
        {col} = EXCLUDED.{col},
        updated_at = EXCLUDED.updated_at
    """

    with db.engine.begin() as conn:
        conn.execute(
            text(sql),
            {"company_id": int(company_id), "year_month": ym, "val": v, "updated_at": _now()},
        )

    return get_company_usage_month(company_id=company_id, year_month=ym)


def increment_company_usage(
    *,
    company_id: int,
    metric: str,
    delta: int = 1,
    year_month: Optional[str] = None,
) -> Dict[str, Any]:
    col = _metric_to_col(metric)
    if not col:
        raise ValueError("Invalid metric")

    ym = (year_month or _ym_utc()).strip()
    d = int(delta)
    if d <= 0:
        d = 1

    # Upsert + atomic increment in one statement
    sql = f"""
    INSERT INTO company_usage_monthly (company_id, year_month, {col}, updated_at)
    VALUES (:company_id, :year_month, :delta, :updated_at)
    ON CONFLICT (company_id, year_month) DO UPDATE SET
        {col} = company_usage_monthly.{col} + EXCLUDED.{col},
        updated_at = EXCLUDED.updated_at
    """

    with db.engine.begin() as conn:
        conn.execute(
            text(sql),
            {"company_id": int(company_id), "year_month": ym, "delta": d, "updated_at": _now()},
        )

    return get_company_usage_month(company_id=company_id, year_month=ym)

# -----------------------------
# ENFORCEMENT
# -----------------------------
@dataclass
class UsageCheckResult:
    allowed: bool
    reason: str
    metric: str
    used: int
    limit: int
    year_month: str
    plan: str


def _limit_for_metric(ent: Entitlements, metric: str) -> Optional[int]:
    """
    Maps the entitlement limit keys to enforcement metrics.
    """
    m = (metric or "").strip()

    # Standardize to entitlement keys
    if m in {"drivers"}:
        key = "drivers"
    elif m in {"team_members"}:
        key = "team_members"
    elif m in {"payroll_runs", "payroll_runs_per_month"}:
        key = "payroll_runs_per_month"
    elif m in {"loads", "loads_per_month"}:
        key = "loads_per_month"
    else:
        return None

    raw = (ent.limits or {}).get(key)
    if raw is None:
        return None

    try:
        v = int(raw)
        return v if v >= 0 else 0
    except Exception:
        return None


def _used_for_metric(usage_row: Dict[str, Any], metric: str) -> int:
    m = (metric or "").strip()
    if m == "drivers":
        return int(usage_row.get("drivers") or 0)
    if m == "team_members":
        return int(usage_row.get("team_members") or 0)
    if m in {"payroll_runs", "payroll_runs_per_month"}:
        return int(usage_row.get("payroll_runs") or 0)
    if m in {"loads", "loads_per_month"}:
        return int(usage_row.get("loads") or 0)
    return 0


def check_usage_limit(*, company_id: int, metric: str, projected_delta: int = 0) -> UsageCheckResult:
    ym = _ym_utc()
    ent = _get_entitlements_for_company(company_id)
    limit = _limit_for_metric(ent, metric)

    usage = get_company_usage_month(company_id=company_id, year_month=ym)
    used = _used_for_metric(usage, metric)
    proj = used + int(projected_delta or 0)

    # If no limit defined, treat as allowed (enterprise/overrides can set huge values anyway)
    if limit is None:
        return UsageCheckResult(
            allowed=True,
            reason="no_limit_defined",
            metric=metric,
            used=used,
            limit=-1,
            year_month=ym,
            plan=ent.plan,
        )

    if proj <= limit:
        return UsageCheckResult(
            allowed=True,
            reason="ok",
            metric=metric,
            used=used,
            limit=limit,
            year_month=ym,
            plan=ent.plan,
        )

    return UsageCheckResult(
        allowed=False,
        reason="limit_exceeded",
        metric=metric,
        used=used,
        limit=limit,
        year_month=ym,
        plan=ent.plan,
    )


def enforce_usage_limit(*, metric: str, delta: int = 1) -> Callable[[F], F]:
    """
    Decorator to enforce plan limits and optionally increment usage.

    Pattern:
      @enforce_usage_limit(metric="payroll_runs_per_month", delta=1)
      def run_payroll(): ...

    Rules:
      - Requires X-Company-Id (preferred) or company_id in query/body
      - Checks entitlements limit for the metric
      - If allowed, increments the usage counter for the current UTC month
    """

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            company_id = _extract_company_id()
            if company_id is None:
                return (
                    jsonify(
                        {
                            "error": "company_id_required",
                            "message": "Missing company_id.",
                            "hint": "Provide X-Company-Id (preferred) or company_id in query/body.",
                        }
                    ),
                    400,
                )

            res = check_usage_limit(company_id=company_id, metric=metric, projected_delta=delta)

            if not res.allowed:
                return (
                    jsonify(
                        {
                            "error": "usage_limit_exceeded",
                            "metric": res.metric,
                            "used": res.used,
                            "limit": res.limit,
                            "year_month": res.year_month,
                            "plan": res.plan,
                        }
                    ),
                    403,
                )

            # Only increment after the check passes (atomic upsert increment)
            increment_company_usage(company_id=company_id, metric=metric, delta=delta, year_month=res.year_month)

            return fn(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


__all__ = [
    "get_company_usage_month",
    "set_company_usage_metric",
    "increment_company_usage",
    "check_usage_limit",
    "enforce_usage_limit",
]

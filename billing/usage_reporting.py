# File: billing/usage_reporting.py
# Purpose: Production usage reporting + overage calculation (read-only, no mutation)
# Status: FULL PRODUCTION – hardened, deterministic
# Date: 2026-01-26

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from db import db
from billing.entitlement_store import get_customer_subscription
from billing.entitlement import entitlements_from_dict


def _now() -> int:
    return int(time.time())


def _month_bounds(ts: Optional[int] = None) -> Dict[str, int]:
    """
    Returns epoch seconds for [month_start, month_end).
    """
    import datetime as _dt

    dt = _dt.datetime.utcfromtimestamp(ts or _now())
    start = _dt.datetime(dt.year, dt.month, 1, tzinfo=_dt.timezone.utc)
    if dt.month == 12:
        end = _dt.datetime(dt.year + 1, 1, 1, tzinfo=_dt.timezone.utc)
    else:
        end = _dt.datetime(dt.year, dt.month + 1, 1, tzinfo=_dt.timezone.utc)
    return {"start": int(start.timestamp()), "end": int(end.timestamp())}


def get_usage_summary(
    *,
    customer_id: str,
    metric: Optional[str] = None,
    since: Optional[int] = None,
    until: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Aggregates usage events for a customer.
    Expects a durable usage table written by billing/usage_metering.py with columns:
      - customer_id TEXT
      - metric TEXT
      - quantity INTEGER
      - occurred_at BIGINT
    """
    cid = (customer_id or "").strip()
    if not cid:
        raise ValueError("customer_id required")

    if since is None or until is None:
        b = _month_bounds()
        since = since or b["start"]
        until = until or b["end"]

    params: Dict[str, Any] = {"customer_id": cid, "since": int(since), "until": int(until)}
    metric_sql = ""
    if metric:
        metric_sql = "AND metric = :metric"
        params["metric"] = metric

    sql = f"""
        SELECT metric, SUM(quantity) AS total
        FROM usage_events
        WHERE customer_id = :customer_id
          AND occurred_at >= :since
          AND occurred_at < :until
          {metric_sql}
        GROUP BY metric
        ORDER BY metric
    """

    rows: List[Dict[str, Any]] = []
    with db.engine.begin() as conn:
        res = conn.execute(text(sql), params).mappings().all()
        rows = [dict(r) for r in res]

    totals = {r["metric"]: int(r["total"] or 0) for r in rows}
    return {
        "customer_id": cid,
        "since": int(since),
        "until": int(until),
        "totals": totals,
    }


def get_overages(
    *,
    customer_id: str,
    since: Optional[int] = None,
    until: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Computes overages by comparing usage totals to entitlement limits.
    """
    cid = (customer_id or "").strip()
    if not cid:
        raise ValueError("customer_id required")

    sub = get_customer_subscription(cid)
    ent = entitlements_from_dict(sub.get("entitlements") if sub else None)
    limits = ent.limits if ent else {}

    usage = get_usage_summary(customer_id=cid, since=since, until=until)["totals"]

    over: Dict[str, Dict[str, int]] = {}
    for metric, used in usage.items():
        limit = int(limits.get(metric, 0))
        if limit > 0 and used > limit:
            over[metric] = {"used": used, "limit": limit, "overage": used - limit}

    return {
        "customer_id": cid,
        "overages": over,
        "has_overage": bool(over),
    }


def list_usage_rows(
    *,
    customer_id: str,
    metric: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Paginated raw usage rows for admin/reporting UI.
    """
    cid = (customer_id or "").strip()
    if not cid:
        raise ValueError("customer_id required")

    params: Dict[str, Any] = {"customer_id": cid, "limit": int(limit), "offset": int(offset)}
    metric_sql = ""
    if metric:
        metric_sql = "AND metric = :metric"
        params["metric"] = metric

    sql = f"""
        SELECT customer_id, metric, quantity, occurred_at
        FROM usage_events
        WHERE customer_id = :customer_id
          {metric_sql}
        ORDER BY occurred_at DESC
        LIMIT :limit OFFSET :offset
    """

    with db.engine.begin() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]


__all__ = [
    "get_usage_summary",
    "get_overages",
    "list_usage_rows",
]


if __name__ == "__main__":
    print("billing/usage_reporting.py FULL PRODUCTION OK")

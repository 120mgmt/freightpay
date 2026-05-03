# File: payroll/audit_routes.py
# Purpose: Payroll audit read API (best-effort; never blocks deploy)
# Status: Production-ready (defensive, tenant-scoped)
# Date: 2026-02-18

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request
from sqlalchemy import text

from db import db

# Blueprint expected by app.py import
payroll_audit_bp = Blueprint("payroll_audit_api_v1", __name__, url_prefix="/payroll/audit")


def _int(v: Any, default: int) -> int:
    try:
        return int(str(v).strip())
    except Exception:
        return default


def _require_company_id() -> int:
    """
    Matches your existing multi-tenant patterns (header/query/body), allows company_id=0.
    """
    cid = (
        request.headers.get("X-Company-Id")
        or request.args.get("company_id")
        or (request.get_json(silent=True) or {}).get("company_id")
    )
    if cid is None or str(cid).strip() == "":
        raise ValueError("Missing company_id (X-Company-Id header, query, or JSON).")
    v = _int(cid, -1)
    if v < 0:
        raise ValueError("company_id must be a non-negative integer.")
    return v


def _json_error(msg: str, code: int = 400, **extra: Any):
    payload: Dict[str, Any] = {"error": msg}
    payload.update(extra)
    return jsonify(payload), code


def _run_query(sql: str, params: Dict[str, Any]) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """
    Returns (rows, error). Uses SQL text so it works regardless of which AuditLog model is in play.
    """
    try:
        with db.engine.begin() as conn:
            res = conn.execute(text(sql), params)
            rows = [dict(r) for r in res.mappings().all()]
            return rows, None
    except Exception as e:
        return None, str(e)


@payroll_audit_bp.get("/health")
def audit_health():
    return jsonify({"ok": True, "service": "payroll_audit", "env": os.getenv("APP_ENV", "production")})


@payroll_audit_bp.get("/logs")
def list_audit_logs():
    """
    Best-effort audit log fetch. If your audit_logs table schema varies, this endpoint still returns rows.
    Query params:
      - company_id (required) via X-Company-Id or ?company_id=
      - limit (default 200, max 1000)
      - action (optional; best-effort)
      - entity (optional; best-effort)
      - entity_id (optional; best-effort)
    """
    try:
        company_id = _require_company_id()
    except Exception as e:
        return _json_error(str(e), 400)

    limit = _int(request.args.get("limit"), 200)
    if limit < 1:
        limit = 1
    if limit > 1000:
        limit = 1000

    action = (request.args.get("action") or "").strip()
    entity = (request.args.get("entity") or "").strip()
    entity_id = (request.args.get("entity_id") or "").strip()

    params: Dict[str, Any] = {"company_id": company_id, "limit": limit}

    # Attempt 1: apply filters for the "models.py" schema (action/entity/entity_id).
    where = ["company_id = :company_id"]
    if action:
        where.append("action = :action")
        params["action"] = action
    if entity:
        where.append("entity = :entity")
        params["entity"] = entity
    if entity_id:
        # entity_id might be int or text depending on schema; compare as text defensively
        where.append("CAST(entity_id AS TEXT) = :entity_id")
        params["entity_id"] = entity_id

    sql1 = f"""
        SELECT *
        FROM audit_logs
        WHERE {" AND ".join(where)}
        ORDER BY created_at DESC NULLS LAST
        LIMIT :limit
    """

    rows, err = _run_query(sql1, params)
    if rows is not None:
        return jsonify({"company_id": company_id, "count": len(rows), "rows": rows})

    # Attempt 2: fallback for other schemas (e.g., uuid id, event_type/metadata/user_id).
    # Drop filter predicates that may not exist; keep tenant + limit only.
    sql2 = """
        SELECT *
        FROM audit_logs
        WHERE company_id = :company_id
        ORDER BY created_at DESC NULLS LAST
        LIMIT :limit
    """
    rows2, err2 = _run_query(sql2, {"company_id": company_id, "limit": limit})
    if rows2 is not None:
        return jsonify(
            {
                "company_id": company_id,
                "count": len(rows2),
                "rows": rows2,
                "note": "Filters unavailable for current audit_logs schema; returned most recent rows.",
            }
        )

    return _json_error(
        "Failed to query audit_logs table.",
        500,
        detail=err2 or err or "unknown_error",
    )

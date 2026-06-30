# File: payroll/routes/payroll_routes.py
# Purpose: Payroll API routes + optional provider submit blueprint (production, durable, tenant-safe)
# Date: 2026-02-23
# Status: FULL PRODUCTION READY (Postgres durable on Render; no /tmp SQLite; company-scoped; entitlement-gated)

from __future__ import annotations

import csv
import io
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import text

from db import db
# NOTE: Subscription enforcement is handled globally by app.py before_request guard
# (utils.subscription_guard.enforce_subscription_active). The per-route decorator
# below is kept for feature-level entitlement checks (e.g. payroll_run feature flag)
# but access control is NOT duplicated — global guard runs first.
from billing.subscription_gate import require_active_subscription
from payroll.engine import run_payroll
from payroll.provider import get_payroll_provider

# ============================================================
# Blueprints
# ============================================================

payroll_bp = Blueprint("payroll_api_v1", __name__, url_prefix="/payroll")

# app.py expects this to exist (it registers it)
provider_submit_bp = Blueprint("provider_submit_api_v1", __name__, url_prefix="/payroll/provider")

# ============================================================
# DB (Postgres / SQLAlchemy engine) — durable on Render
# NOTE: Do NOT rely on import-time DB init. Ensure tables exist lazily at request time.
# ============================================================

# payroll_runs table is managed by Alembic migration:
# migrations/versions/20260401_payroll_runs.py
# Run: flask db upgrade
# Do NOT define DDL here.

_DB_READY: bool = True  # Table exists via migration


def _ensure_db_ready() -> None:
    """No-op: payroll_runs table is created by Alembic migration."""
    pass


# ============================================================
# Utilities
# ============================================================

def _now_epoch() -> int:
    return int(time.time())


def _utc_iso(ts: Optional[int] = None) -> str:
    t = int(ts if ts is not None else _now_epoch())
    return datetime.fromtimestamp(t, tz=timezone.utc).isoformat()


def _parse_json() -> Dict[str, Any]:
    if not request.is_json:
        return {}
    try:
        v = request.get_json(force=True)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def _json_error(msg: str, code: int = 400, **extra: Any):
    payload: Dict[str, Any] = {"error": msg}
    payload.update(extra)
    return jsonify(payload), code


def _require_company_id(data: Dict[str, Any]) -> int:
    """
    Allows company_id=0 (your environment uses it).
    """
    cid = (
        request.headers.get("X-Company-Id")
        or request.args.get("company_id")
        or data.get("company_id")
    )
    if cid is None or str(cid).strip() == "":
        raise ValueError("Missing company_id (X-Company-Id header, query, or JSON).")
    try:
        v = int(str(cid).strip())
        if v < 0:
            raise ValueError("company_id must be a non-negative integer.")
        return v
    except Exception:
        raise ValueError("company_id must be an integer.")


# ============================================================
# HEALTH
# ============================================================

@payroll_bp.get("/health")
def payroll_health():
    try:
        with db.engine.begin() as conn:
            conn.execute(text("SELECT 1"))
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500


# ============================================================
# CREATE PAYROLL RUN
# ============================================================

@payroll_bp.route("/runs", methods=["POST"])
@require_active_subscription(feature="payroll_run")
def payroll_create_run():
    payload = _parse_json()
    if not payload:
        return _json_error("Invalid or missing JSON payload")

    try:
        company_id = _require_company_id(payload)
    except Exception as e:
        return _json_error("invalid_request", 400, detail=str(e))

    _ensure_db_ready()

    run_id = str(uuid.uuid4())
    created_at = _now_epoch()

    try:
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO payroll_runs (run_id, company_id, created_at, status, payload_json, finalized)
                    VALUES (:run_id, :company_id, :created_at, :status, :payload_json, FALSE)
                    """
                ),
                {
                    "run_id": run_id,
                    "company_id": company_id,
                    "created_at": created_at,
                    "status": "pending",
                    "payload_json": json.dumps(payload),
                },
            )
    except Exception as e:
        return _json_error("db_error", 500, detail=str(e))

    return (
        jsonify(
            {
                "run_id": run_id,
                "company_id": company_id,
                "status": "pending",
                "created_at": _utc_iso(created_at),
            }
        ),
        201,
    )


# ============================================================
# EXECUTE PAYROLL RUN
# ============================================================

@payroll_bp.route("/runs/<run_id>/execute", methods=["POST"])
@require_active_subscription(feature="payroll_run")
def payroll_execute_run(run_id: str):
    data = _parse_json()
    try:
        company_id = _require_company_id(data)
    except Exception as e:
        return _json_error("invalid_request", 400, detail=str(e))

    _ensure_db_ready()

    try:
        with db.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT payload_json, finalized
                    FROM payroll_runs
                    WHERE run_id = :run_id AND company_id = :company_id
                    """
                ),
                {"run_id": run_id, "company_id": company_id},
            ).mappings().fetchone()

            if not row:
                return _json_error("Run not found", 404)

            if bool(row.get("finalized")):
                return _json_error("Run already finalized", 409)

            payload = json.loads(row["payload_json"]) if row.get("payload_json") else {}
            results = run_payroll(payload)

            conn.execute(
                text(
                    """
                    UPDATE payroll_runs
                    SET status = :status, results_json = :results_json
                    WHERE run_id = :run_id AND company_id = :company_id
                    """
                ),
                {
                    "status": "completed",
                    "results_json": json.dumps(results, default=str),
                    "run_id": run_id,
                    "company_id": company_id,
                },
            )
    except Exception as e:
        return _json_error("db_error", 500, detail=str(e))

    return jsonify({"run_id": run_id, "company_id": company_id, "status": "completed", "results": results}), 200


# ============================================================
# EXECUTE + MAP TO PROVIDER (PAYLOAD ONLY)
# ============================================================

@payroll_bp.route("/runs/<run_id>/execute-provider-map", methods=["POST"])
@require_active_subscription(feature="payroll_run")
def payroll_execute_run_provider_map(run_id: str):
    data = _parse_json()
    try:
        company_id = _require_company_id(data)
    except Exception as e:
        return _json_error("invalid_request", 400, detail=str(e))

    _ensure_db_ready()

    try:
        with db.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT payload_json, results_json, status, finalized
                    FROM payroll_runs
                    WHERE run_id = :run_id AND company_id = :company_id
                    """
                ),
                {"run_id": run_id, "company_id": company_id},
            ).mappings().fetchone()

            if not row:
                return _json_error("Run not found", 404)

            if bool(row.get("finalized")):
                return _json_error("Run already finalized", 409)

            payload = json.loads(row["payload_json"]) if row.get("payload_json") else {}
            results = json.loads(row["results_json"]) if row.get("results_json") else None

            if not results:
                results = run_payroll(payload)
                conn.execute(
                    text(
                        """
                        UPDATE payroll_runs
                        SET status = :status, results_json = :results_json
                        WHERE run_id = :run_id AND company_id = :company_id
                        """
                    ),
                    {
                        "status": "completed",
                        "results_json": json.dumps(results, default=str),
                        "run_id": run_id,
                        "company_id": company_id,
                    },
                )
    except Exception as e:
        return _json_error("db_error", 500, detail=str(e))

    provider_payloads: List[Dict[str, Any]] = []
    provider = get_payroll_provider()

    for r in (results.get("results") or []):
        if not isinstance(r, dict):
            continue

        worker_uuid = str(r.get("worker_uuid") or "").strip()
        worker_type = str(r.get("worker_type") or "").strip()

        if not worker_uuid or worker_type not in ("contractor", "employee"):
            contractor_id = str(r.get("contractor_id") or "").strip()
            for c in (payload.get("contractors", []) or []):
                if str(c.get("contractor_id") or "").strip() == contractor_id:
                    worker_uuid = str(c.get("worker_uuid") or "").strip() or worker_uuid
                    worker_type = str(c.get("worker_type") or "").strip() or worker_type
                    break

        if not worker_uuid or worker_type not in ("contractor", "employee"):
            continue

        provider_payloads.append(provider.build_provider_payload(r))

    return (
        jsonify(
            {
                "run_id": run_id,
                "company_id": company_id,
                "status": "completed",
                "provider_payloads": provider_payloads,
                "results": results,
            }
        ),
        200,
    )


# ============================================================
# GET SINGLE RUN
# ============================================================

@payroll_bp.route("/runs/<run_id>", methods=["GET"])
@require_active_subscription(feature="payroll_run")
def payroll_get_run(run_id: str):
    try:
        company_id = _require_company_id({})
    except Exception as e:
        return _json_error("invalid_request", 400, detail=str(e))

    _ensure_db_ready()

    try:
        with db.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT run_id, company_id, created_at, payload_json, results_json,
                           status, finalized, finalized_at
                    FROM payroll_runs
                    WHERE run_id = :run_id AND company_id = :company_id
                    """
                ),
                {"run_id": run_id, "company_id": company_id},
            ).mappings().fetchone()
    except Exception as e:
        return _json_error("db_error", 500, detail=str(e))

    if not row:
        return _json_error("Run not found", 404)

    return jsonify(
        {
            "run_id": row["run_id"],
            "company_id": row["company_id"],
            "created_at": _utc_iso(int(row["created_at"])),
            "status": row["status"],
            "finalized": bool(row["finalized"]),
            "finalized_at": _utc_iso(int(row["finalized_at"])) if row.get("finalized_at") else None,
            "payload": json.loads(row["payload_json"]) if row.get("payload_json") else None,
            "results": json.loads(row["results_json"]) if row.get("results_json") else None,
        }
    ), 200


# ============================================================
# LIST RUNS
# ============================================================

@payroll_bp.route("/runs", methods=["GET"])
@require_active_subscription(feature="payroll_run")
def payroll_list_runs():
    try:
        company_id = _require_company_id({})
    except Exception as e:
        return _json_error("invalid_request", 400, detail=str(e))

    _ensure_db_ready()

    try:
        limit = int(request.args.get("limit", 20))
        limit = max(1, min(limit, 200))
    except Exception:
        limit = 20

    try:
        with db.engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT run_id, created_at, status, finalized
                    FROM payroll_runs
                    WHERE company_id = :company_id
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"company_id": company_id, "limit": limit},
            ).mappings().fetchall()
    except Exception as e:
        return _json_error("db_error", 500, detail=str(e))

    return jsonify(
        {
            "company_id": company_id,
            "runs": [
                {
                    "run_id": r["run_id"],
                    "created_at": _utc_iso(int(r["created_at"])),
                    "status": r["status"],
                    "finalized": bool(r["finalized"]),
                }
                for r in rows
            ],
        }
    ), 200


# ============================================================
# RUN STATUS (LIGHTWEIGHT)
# ============================================================

@payroll_bp.route("/runs/<run_id>/status", methods=["GET"])
@require_active_subscription(feature="payroll_run")
def payroll_run_status(run_id: str):
    try:
        company_id = _require_company_id({})
    except Exception as e:
        return _json_error("invalid_request", 400, detail=str(e))

    _ensure_db_ready()

    try:
        with db.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT run_id, status, finalized, finalized_at
                    FROM payroll_runs
                    WHERE run_id = :run_id AND company_id = :company_id
                    """
                ),
                {"run_id": run_id, "company_id": company_id},
            ).mappings().fetchone()
    except Exception as e:
        return _json_error("db_error", 500, detail=str(e))

    if not row:
        return _json_error("Run not found", 404)

    return jsonify(
        {
            "run_id": row["run_id"],
            "company_id": company_id,
            "status": row["status"],
            "finalized": bool(row["finalized"]),
            "finalized_at": _utc_iso(int(row["finalized_at"])) if row.get("finalized_at") else None,
        }
    ), 200


# ============================================================
# FINALIZE RUN
# ============================================================

@payroll_bp.route("/runs/<run_id>/finalize", methods=["POST"])
@require_active_subscription(feature="payroll_finalize")
def payroll_finalize_run(run_id: str):
    data = _parse_json()
    try:
        company_id = _require_company_id(data)
    except Exception as e:
        return _json_error("invalid_request", 400, detail=str(e))

    _ensure_db_ready()

    finalized_at = _now_epoch()

    try:
        with db.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT finalized
                    FROM payroll_runs
                    WHERE run_id = :run_id AND company_id = :company_id
                    """
                ),
                {"run_id": run_id, "company_id": company_id},
            ).mappings().fetchone()

            if not row:
                return _json_error("Run not found", 404)

            if bool(row.get("finalized")):
                return _json_error("Run already finalized", 409)

            conn.execute(
                text(
                    """
                    UPDATE payroll_runs
                    SET finalized = TRUE,
                        finalized_at = :finalized_at
                    WHERE run_id = :run_id AND company_id = :company_id
                    """
                ),
                {"finalized_at": finalized_at, "run_id": run_id, "company_id": company_id},
            )
    except Exception as e:
        return _json_error("db_error", 500, detail=str(e))

    return jsonify(
        {"run_id": run_id, "company_id": company_id, "finalized": True, "finalized_at": _utc_iso(finalized_at)}
    ), 200


# ============================================================
# EXPORT RESULTS (CSV)
# ============================================================

@payroll_bp.route("/runs/<run_id>/export", methods=["GET"])
@require_active_subscription(feature="payroll_export_csv")
def payroll_export_run(run_id: str):
    try:
        company_id = _require_company_id({})
    except Exception as e:
        return _json_error("invalid_request", 400, detail=str(e))

    _ensure_db_ready()

    try:
        with db.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT results_json
                    FROM payroll_runs
                    WHERE run_id = :run_id AND company_id = :company_id
                    """
                ),
                {"run_id": run_id, "company_id": company_id},
            ).mappings().fetchone()
    except Exception as e:
        return _json_error("db_error", 500, detail=str(e))

    if not row or not row.get("results_json"):
        return _json_error("No results available", 404)

    results_obj = json.loads(row["results_json"])
    rows = (results_obj.get("results") or []) if isinstance(results_obj, dict) else []
    totals = results_obj.get("totals") if isinstance(results_obj, dict) else None

    output = io.StringIO()
    writer = csv.writer(output)

    headers = ["contractor_id", "base_gross", "accessorials_total", "deductions_total", "gross", "net"]
    writer.writerow(headers)

    for item in rows:
        if not isinstance(item, dict):
            continue
        access_total = ((item.get("accessorials") or {}).get("total")) if isinstance(item.get("accessorials"), dict) else ""
        ded_total = ((item.get("deductions") or {}).get("total")) if isinstance(item.get("deductions"), dict) else ""
        writer.writerow(
            [
                item.get("contractor_id", ""),
                item.get("base_gross", ""),
                access_total,
                ded_total,
                item.get("gross", ""),
                item.get("net", ""),
            ]
        )

    if isinstance(totals, dict):
        writer.writerow([])
        writer.writerow(["TOTALS", "", "", "", "", ""])
        writer.writerow(
            [
                "",
                totals.get("base_gross", ""),
                totals.get("accessorials", ""),
                totals.get("deductions", ""),
                totals.get("gross", ""),
                totals.get("net", ""),
            ]
        )

    output.seek(0)

    return Response(
        output.read(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=payroll_{run_id}.csv"},
    )


# ============================================================
# OPTIONAL: PROVIDER SUBMIT (PRODUCTION-SAFE FAIL)
# ============================================================

@provider_submit_bp.route("/submit", methods=["POST"])
@require_active_subscription(feature="integrations_payroll_provider")
def provider_submit():
    """
    This endpoint intentionally returns 501 until a real provider submitter is wired.
    Prevents false positives in production.
    """
    payload = _parse_json()
    provider_payloads = payload.get("provider_payloads")

    if not isinstance(provider_payloads, list) or not provider_payloads:
        return _json_error("Missing provider_payloads (list)", 400)

    return _json_error("Provider submission not configured in this deployment", 501)


__all__ = ["payroll_bp", "provider_submit_bp"]

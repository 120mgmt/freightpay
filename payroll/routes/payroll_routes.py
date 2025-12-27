# payroll/routes/payroll_routes.py
from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, Response, jsonify, request

from payroll.engine import run_payroll

# IMPORTANT: subscription gate import must match where the billing package lives in the repo.
# This handles BOTH layouts safely:
#  - billing/subscription_gate.py
#  - billing/subscription_gate.py
try:
    from billing.subscription_gate import require_active_subscription
except ModuleNotFoundError:
    from billing.subscription_gate import require_active_subscription  # type: ignore


# ✅ Unique blueprint name (prevents "already registered" errors)
payroll_bp = Blueprint("payroll_api_v1", __name__, url_prefix="/payroll")

# ✅ Zero-new-deps persistence (SQLite)
# Render filesystem is ephemeral; /tmp works for runtime persistence between requests.
DB_PATH = os.getenv("PAYROLL_DB_PATH", "/tmp/payroll.db")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    conn = _db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payroll_runs (
                run_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL,
                finalized_at TEXT,
                payload_json TEXT NOT NULL,
                results_json TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


_init_db()


def _write_run(
    *,
    run_id: str,
    status: str,
    payload: Dict[str, Any],
    results: Dict[str, Any],
    finalized_at: Optional[str] = None,
) -> None:
    created_at = _utc_now_iso()
    updated_at = created_at

    conn = _db()
    try:
        conn.execute(
            """
            INSERT INTO payroll_runs (run_id, created_at, updated_at, status, finalized_at, payload_json, results_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                created_at,
                updated_at,
                status,
                finalized_at,
                json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
                json.dumps(results, separators=(",", ":"), ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _update_run(
    *,
    run_id: str,
    status: Optional[str] = None,
    results: Optional[Dict[str, Any]] = None,
    finalized_at: Optional[str] = None,
) -> bool:
    fields: List[str] = ["updated_at = ?"]
    params: List[Any] = [_utc_now_iso()]

    if status is not None:
        fields.append("status = ?")
        params.append(status)

    if finalized_at is not None:
        fields.append("finalized_at = ?")
        params.append(finalized_at)

    if results is not None:
        fields.append("results_json = ?")
        params.append(json.dumps(results, separators=(",", ":"), ensure_ascii=False))

    params.append(run_id)

    conn = _db()
    try:
        cur = conn.execute(
            f"UPDATE payroll_runs SET {', '.join(fields)} WHERE run_id = ?",
            tuple(params),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def _get_run_row(run_id: str) -> Optional[sqlite3.Row]:
    conn = _db()
    try:
        row = conn.execute(
            """
            SELECT run_id, created_at, updated_at, status, finalized_at, payload_json, results_json
            FROM payroll_runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        return row
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "run_id": row["run_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "status": row["status"],
        "finalized_at": row["finalized_at"],
        "payload": json.loads(row["payload_json"]),
        "results": json.loads(row["results_json"]),
    }


def _csv_from_results(results_obj: Dict[str, Any]) -> str:
    """
    Accepts results object saved in DB:
      {
        "results": [...],
        "totals": {...}
      }
    """
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(
        [
            "contractor_id",
            "base_gross",
            "accessorials_total",
            "deductions_total",
            "gross",
            "net",
        ]
    )

    rows = results_obj.get("results") or []
    if isinstance(rows, dict) and "results" in rows:
        rows = rows.get("results") or []

    if not isinstance(rows, list):
        rows = []

    for r in rows:
        if not isinstance(r, dict):
            continue

        base_gross = r.get("base_gross", 0)
        gross = r.get("gross", 0)
        net = r.get("net", 0)

        access = r.get("accessorials") or {}
        deductions = r.get("deductions") or {}

        access_total = 0
        deductions_total = 0

        if isinstance(access, dict):
            access_total = access.get("total", 0)
        if isinstance(deductions, dict):
            deductions_total = deductions.get("total", 0)

        writer.writerow(
            [
                r.get("contractor_id", ""),
                base_gross,
                access_total,
                deductions_total,
                gross,
                net,
            ]
        )

    return output.getvalue()


@payroll_bp.route("/run", methods=["POST"])
@require_active_subscription
def payroll_run() -> Tuple[Response, int]:
    """
    POST /payroll/run
    Body: { "contractors": [ ... ] }
    Persists run + returns run_id + results
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid JSON body. Send application/json."}), 400

    contractors = payload.get("contractors")
    if not isinstance(contractors, list):
        return jsonify({"error": "Missing/invalid 'contractors' (must be a list)."}), 400

    # Run payroll engine
    results = run_payroll(payload)

    run_id = str(uuid.uuid4())
    _write_run(
        run_id=run_id,
        status="computed",
        payload=payload,
        results=results,
        finalized_at=None,
    )

    return jsonify({"run_id": run_id, "status": "computed", "results": results}), 200


@payroll_bp.route("/runs/<run_id>", methods=["GET"])
@require_active_subscription
def payroll_get_run(run_id: str) -> Tuple[Response, int]:
    row = _get_run_row(run_id)
    if not row:
        return jsonify({"error": "Run not found"}), 404
    return jsonify(_row_to_dict(row)), 200


@payroll_bp.route("/runs", methods=["GET"])
@require_active_subscription
def payroll_list_runs() -> Tuple[Response, int]:
    limit = request.args.get("limit", "20")
    try:
        limit_i = max(1, min(200, int(limit)))
    except ValueError:
        limit_i = 20

    conn = _db()
    try:
        rows = conn.execute(
            """
            SELECT run_id, created_at, updated_at, status, finalized_at
            FROM payroll_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit_i,),
        ).fetchall()
    finally:
        conn.close()

    return (
        jsonify(
            {
                "runs": [
                    {
                        "run_id": r["run_id"],
                        "created_at": r["created_at"],
                        "updated_at": r["updated_at"],
                        "status": r["status"],
                        "finalized_at": r["finalized_at"],
                    }
                    for r in rows
                ]
            }
        ),
        200,
    )


@payroll_bp.route("/runs/<run_id>/status", methods=["GET"])
@require_active_subscription
def payroll_run_status(run_id: str) -> Tuple[Response, int]:
    row = _get_run_row(run_id)
    if not row:
        return jsonify({"error": "Run not found"}), 404

    return (
        jsonify(
            {
                "run_id": row["run_id"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "finalized_at": row["finalized_at"],
            }
        ),
        200,
    )


@payroll_bp.route("/runs/<run_id>/finalize", methods=["POST"])
@require_active_subscription
def payroll_finalize(run_id: str) -> Tuple[Response, int]:
    row = _get_run_row(run_id)
    if not row:
        return jsonify({"error": "Run not found"}), 404

    if row["status"] == "finalized":
        return jsonify({"run_id": run_id, "status": "finalized", "finalized_at": row["finalized_at"]}), 200

    finalized_at = _utc_now_iso()
    ok = _update_run(run_id=run_id, status="finalized", finalized_at=finalized_at)
    if not ok:
        return jsonify({"error": "Failed to finalize run"}), 500

    return jsonify({"run_id": run_id, "status": "finalized", "finalized_at": finalized_at}), 200


@payroll_bp.route("/runs/<run_id>/export.csv", methods=["GET"])
@require_active_subscription
def payroll_export_csv(run_id: str) -> Tuple[Response, int]:
    row = _get_run_row(run_id)
    if not row:
        return jsonify({"error": "Run not found"}), 404

    results_obj = json.loads(row["results_json"])
    csv_text = _csv_from_results(results_obj)

    return (
        Response(
            csv_text,
            mimetype="text/csv",
            headers={"Content-Disposition": f'attachment; filename="payroll_run_{run_id}.csv"'},
        ),
        200,
    )

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

# Subscription gate (already exists in repo)
from billing.subscription_gate import require_active_subscription

# ============================================================
# Blueprint
# ============================================================

payroll_bp = Blueprint(
    "payroll_api_v1",
    __name__,
    url_prefix="/payroll",
)

# ============================================================
# Database (SQLite – zero-dependency, Render-safe)
# ============================================================

DB_PATH = os.getenv("PAYROLL_DB_PATH", "/tmp/payroll.db")


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(
    conn: sqlite3.Connection,
    table: str,
    col: str,
    col_def: str,
) -> None:
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
        conn.commit()
    except sqlite3.OperationalError:
        pass


def _init_db() -> None:
    conn = _db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payroll_runs (
                run_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT,
                results_json TEXT,
                finalized INTEGER DEFAULT 0,
                finalized_at TEXT
            )
            """
        )

        # Forward-compatible columns
        _ensure_column(conn, "payroll_runs", "finalized", "INTEGER DEFAULT 0")
        _ensure_column(conn, "payroll_runs", "finalized_at", "TEXT")

        conn.commit()
    finally:
        conn.close()


_init_db()

# ============================================================
# Utilities
# ============================================================


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json() -> Dict[str, Any]:
    if not request.is_json:
        return {}
    try:
        return request.get_json(force=True)
    except Exception:
        return {}


def _json_error(msg: str, code: int = 400):
    return jsonify({"error": msg}), code


# ============================================================
# CREATE PAYROLL RUN
# ============================================================

@payroll_bp.route("/runs", methods=["POST"])
@require_active_subscription()
def payroll_create_run():
    payload = _parse_json()
    if not payload:
        return _json_error("Invalid or missing JSON payload")

    run_id = str(uuid.uuid4())
    created_at = _utcnow()

    conn = _db()
    try:
        conn.execute(
            """
            INSERT INTO payroll_runs
            (run_id, created_at, status, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                run_id,
                created_at,
                "pending",
                json.dumps(payload),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify(
        {
            "run_id": run_id,
            "status": "pending",
            "created_at": created_at,
        }
    ), 201


# ============================================================
# EXECUTE PAYROLL RUN
# ============================================================

@payroll_bp.route("/runs/<run_id>/execute", methods=["POST"])
@require_active_subscription()
def payroll_execute_run(run_id: str):
    conn = _db()
    try:
        row = conn.execute(
            "SELECT payload_json, finalized FROM payroll_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()

        if not row:
            return _json_error("Run not found", 404)

        if row["finalized"]:
            return _json_error("Run already finalized", 409)

        payload = json.loads(row["payload_json"])
        results = run_payroll(payload)

        conn.execute(
            """
            UPDATE payroll_runs
            SET status = ?, results_json = ?
            WHERE run_id = ?
            """,
            (
                "completed",
                json.dumps(results),
                run_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify(
        {
            "run_id": run_id,
            "status": "completed",
            "results": results,
        }
    ), 200


# ============================================================
# GET SINGLE RUN
# ============================================================

@payroll_bp.route("/runs/<run_id>", methods=["GET"])
@require_active_subscription()
def payroll_get_run(run_id: str):
    conn = _db()
    try:
        row = conn.execute(
            """
            SELECT run_id, created_at, payload_json, results_json,
                   status, finalized, finalized_at
            FROM payroll_runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return _json_error("Run not found", 404)

    return jsonify(
        {
            "run_id": row["run_id"],
            "created_at": row["created_at"],
            "status": row["status"],
            "finalized": bool(row["finalized"]),
            "finalized_at": row["finalized_at"],
            "payload": json.loads(row["payload_json"])
            if row["payload_json"]
            else None,
            "results": json.loads(row["results_json"])
            if row["results_json"]
            else None,
        }
    ), 200


# ============================================================
# LIST RUNS
# ============================================================

@payroll_bp.route("/runs", methods=["GET"])
@require_active_subscription()
def payroll_list_runs():
    limit = int(request.args.get("limit", 20))

    conn = _db()
    try:
        rows = conn.execute(
            """
            SELECT run_id, created_at, status, finalized
            FROM payroll_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    return jsonify(
        {
            "runs": [
                {
                    "run_id": r["run_id"],
                    "created_at": r["created_at"],
                    "status": r["status"],
                    "finalized": bool(r["finalized"]),
                }
                for r in rows
            ]
        }
    ), 200


# ============================================================
# RUN STATUS (LIGHTWEIGHT)
# ============================================================

@payroll_bp.route("/runs/<run_id>/status", methods=["GET"])
@require_active_subscription()
def payroll_run_status(run_id: str):
    conn = _db()
    try:
        row = conn.execute(
            """
            SELECT run_id, status, finalized, finalized_at
            FROM payroll_runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return _json_error("Run not found", 404)

    return jsonify(
        {
            "run_id": row["run_id"],
            "status": row["status"],
            "finalized": bool(row["finalized"]),
            "finalized_at": row["finalized_at"],
        }
    ), 200


# ============================================================
# FINALIZE RUN
# ============================================================

@payroll_bp.route("/runs/<run_id>/finalize", methods=["POST"])
@require_active_subscription()
def payroll_finalize_run(run_id: str):
    conn = _db()
    try:
        row = conn.execute(
            """
            SELECT finalized
            FROM payroll_runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()

        if not row:
            return _json_error("Run not found", 404)

        if row["finalized"]:
            return _json_error("Run already finalized", 409)

        finalized_at = _utcnow()

        conn.execute(
            """
            UPDATE payroll_runs
            SET finalized = 1,
                finalized_at = ?
            WHERE run_id = ?
            """,
            (finalized_at, run_id),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify(
        {
            "run_id": run_id,
            "finalized": True,
            "finalized_at": finalized_at,
        }
    ), 200


# ============================================================
# EXPORT RESULTS (CSV)
# ============================================================

@payroll_bp.route("/runs/<run_id>/export", methods=["GET"])
@require_active_subscription()
def payroll_export_run(run_id: str):
    conn = _db()
    try:
        row = conn.execute(
            """
            SELECT results_json
            FROM payroll_runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row or not row["results_json"]:
        return _json_error("No results available", 404)

    results = json.loads(row["results_json"])

    output = io.StringIO()
    writer = csv.writer(output)

    headers_written = False

    for item in results:
        if isinstance(item, dict):
            if not headers_written:
                writer.writerow(item.keys())
                headers_written = True
            writer.writerow(item.values())

    output.seek(0)

    return Response(
        output.read(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=payroll_{run_id}.csv"
        },
    )

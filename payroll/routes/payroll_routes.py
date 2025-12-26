# payroll/routes/payroll_routes.py
import os
import json
import uuid
import sqlite3
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, Response

from payroll.engine import run_payroll
from payroll.export_csv import settlements_to_csv
from billing.subscription_gate import require_active_subscription

# Blueprint (versioned, safe to register once)
payroll_bp = Blueprint("payroll_api_v1", __name__, url_prefix="/payroll")

# SQLite persistence (swap later for Postgres without refactor)
DB_PATH = os.getenv("PAYROLL_DB_PATH", "/tmp/payroll.db")


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    conn = _db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payroll_runs (
                run_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                results_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                finalized_at TEXT,
                finalized_by TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


_init_db()


# -----------------------
# RUN PAYROLL
# -----------------------
@payroll_bp.route("/run", methods=["POST"])
@require_active_subscription()
def payroll_run():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    contractors = payload.get("contractors")
    if not isinstance(contractors, list):
        return jsonify({"error": "Missing/invalid contractors list"}), 400

    results = run_payroll(payload)
    if "error" in results:
        return jsonify(results), 400

    run_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    conn = _db()
    try:
        conn.execute(
            """
            INSERT INTO payroll_runs (
                run_id,
                created_at,
                payload_json,
                results_json,
                status
            )
            VALUES (?, ?, ?, ?, 'draft')
            """,
            (
                run_id,
                created_at,
                json.dumps(payload),
                json.dumps(results),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify(
        {
            "run_id": run_id,
            "created_at": created_at,
            "status": "draft",
            "results": results,
        }
    ), 200


# -----------------------
# FINALIZE PAYROLL
# -----------------------
@payroll_bp.route("/finalize", methods=["POST"])
@require_active_subscription()
def payroll_finalize():
    data = request.get_json(silent=True) or {}
    run_id = data.get("run_id")
    user_id = data.get("user_id")

    if not run_id or not user_id:
        return jsonify({"error": "run_id and user_id required"}), 400

    finalized_at = datetime.now(timezone.utc).isoformat()

    conn = _db()
    try:
        row = conn.execute(
            "SELECT status FROM payroll_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()

        if not row:
            return jsonify({"error": "Run not found"}), 404

        if row["status"] != "draft":
            return jsonify({"error": "Run already finalized or locked"}), 400

        conn.execute(
            """
            UPDATE payroll_runs
            SET status = 'finalized',
                finalized_at = ?,
                finalized_by = ?
            WHERE run_id = ?
            """,
            (finalized_at, user_id, run_id),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify(
        {
            "run_id": run_id,
            "status": "finalized",
            "finalized_at": finalized_at,
            "finalized_by": user_id,
        }
    ), 200


# -----------------------
# GET SINGLE RUN
# -----------------------
@payroll_bp.route("/runs/<run_id>", methods=["GET"])
@require_active_subscription()
def payroll_get_run(run_id: str):
    conn = _db()
    try:
        row = conn.execute(
            """
            SELECT *
            FROM payroll_runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify({"error": "Run not found"}), 404

    return jsonify(
        {
            "run_id": row["run_id"],
            "created_at": row["created_at"],
            "status": row["status"],
            "finalized_at": row["finalized_at"],
            "finalized_by": row["finalized_by"],
            "payload": json.loads(row["payload_json"]),
            "results": json.loads(row["results_json"]),
        }
    ), 200


# -----------------------
# LIST RUNS
# -----------------------
@payroll_bp.route("/runs", methods=["GET"])
@require_active_subscription()
def payroll_list_runs():
    limit = request.args.get("limit", "20")
    try:
        limit_i = max(1, min(200, int(limit)))
    except ValueError:
        limit_i = 20

    conn = _db()
    try:
        rows = conn.execute(
            """
            SELECT run_id, created_at, status
            FROM payroll_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit_i,),
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
                }
                for r in rows
            ]
        }
    ), 200


# -----------------------
# EXPORT CSV
# -----------------------
@payroll_bp.route("/runs/<run_id>/export", methods=["GET"])
@require_active_subscription()
def payroll_export_csv(run_id: str):
    conn = _db()
    try:
        row = conn.execute(
            "SELECT results_json FROM payroll_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify({"error": "Run not found"}), 404

    results = json.loads(row["results_json"])
    csv_data = settlements_to_csv(results)

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=payroll_{run_id}.csv"
        },
    )

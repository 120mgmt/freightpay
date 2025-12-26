# payroll/routes/payroll_routes.py
import os
import json
import uuid
import sqlite3
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, Response

from payroll.engine import run_payroll
from payroll.export_csv import settlements_to_csv

# ✅ Unique blueprint name (prevents "already registered" errors)
payroll_bp = Blueprint("payroll_api_v1", __name__, url_prefix="/payroll")

# ✅ Zero-new-deps persistence (SQLite)
DB_PATH = os.getenv("PAYROLL_DB_PATH", "/tmp/payroll.db")


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, col: str, col_def: str) -> None:
    # Adds column if missing (safe no-op if already exists)
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
        conn.commit()
    except sqlite3.OperationalError:
        # column already exists OR sqlite doesn't allow alter in some edge cases
        pass


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
                status TEXT NOT NULL DEFAULT 'created',
                finalized INTEGER NOT NULL DEFAULT 0,
                finalized_at TEXT
            )
            """
        )
        conn.commit()

        # Backward compatible upgrades if table existed before
        _ensure_column(conn, "payroll_runs", "status", "TEXT NOT NULL DEFAULT 'created'")
        _ensure_column(conn, "payroll_runs", "finalized", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "payroll_runs", "finalized_at", "TEXT")
    finally:
        conn.close()


_init_db()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@payroll_bp.route("/run", methods=["POST"])
def payroll_run():
    # Expect JSON body: { "contractors": [ ... ] }
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid JSON body. Send application/json."}), 400

    contractors = payload.get("contractors")
    if not isinstance(contractors, list):
        return jsonify({"error": "Missing/invalid 'contractors' (must be a list)."}), 400

    # Run payroll engine
    results = run_payroll(payload)

    run_id = str(uuid.uuid4())
    created_at = _utc_now_iso()

    # Persist payload + results
    conn = _db()
    try:
        conn.execute(
            """
            INSERT INTO payroll_runs (run_id, created_at, payload_json, results_json, status, finalized, finalized_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                created_at,
                json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
                json.dumps(results, separators=(",", ":"), ensure_ascii=False),
                "calculated",
                0,
                None,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify(
        {
            "run_id": run_id,
            "created_at": created_at,
            "status": "calculated",
            "finalized": False,
            "results": results,
        }
    ), 200


@payroll_bp.route("/runs/<run_id>", methods=["GET"])
def payroll_get_run(run_id: str):
    conn = _db()
    try:
        row = conn.execute(
            "SELECT run_id, created_at, payload_json, results_json, status, finalized, finalized_at "
            "FROM payroll_runs WHERE run_id = ?",
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
            "finalized": bool(row["finalized"]),
            "finalized_at": row["finalized_at"],
            "payload": json.loads(row["payload_json"]),
            "results": json.loads(row["results_json"]),
        }
    ), 200


@payroll_bp.route("/runs", methods=["GET"])
def payroll_list_runs():
    limit = request.args.get("limit", "20")
    try:
        limit_i = max(1, min(200, int(limit)))
    except ValueError:
        limit_i = 20

    conn = _db()
    try:
        rows = conn.execute(
            "SELECT run_id, created_at, status, finalized FROM payroll_runs "
            "ORDER BY created_at DESC LIMIT ?",
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
                    "finalized": bool(r["finalized"]),
                }
                for r in rows
            ]
        }
    ), 200


@payroll_bp.route("/runs/<run_id>/status", methods=["GET"])
def payroll_run_status(run_id: str):
    conn = _db()
    try:
        row = conn.execute(
            "SELECT run_id, status, finalized, finalized_at FROM payroll_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify({"error": "Run not found"}), 404

    return jsonify(
        {
            "run_id": row["run_id"],
            "status": row["status"],
            "finalized": bool(row["finalized"]),
            "finalized_at": row["finalized_at"],
        }
    ), 200


@payroll_bp.route("/runs/<run_id>/finalize", methods=["POST"])
def payroll_finalize_run(run_id: str):
    conn = _db()
    try:
        row = conn.execute(
            "SELECT run_id, finalized FROM payroll_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()

        if not row:
            return jsonify({"error": "Run not found"}), 404

        if bool(row["finalized"]):
            return jsonify({"run_id": run_id, "finalized": True}), 200

        finalized_at = _utc_now_iso()
        conn.execute(
            "UPDATE payroll_runs SET finalized = 1, finalized_at = ?, status = ? WHERE run_id = ?",
            (finalized_at, "finalized", run_id),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"run_id": run_id, "finalized": True, "finalized_at": finalized_at}), 200


@payroll_bp.route("/runs/<run_id>/export.csv", methods=["GET"])
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

    results_obj = json.loads(row["results_json"])
    results_list = results_obj.get("results", [])
    csv_data = settlements_to_csv(results_list)

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="payroll_{run_id}.csv"'},
    )


    

# payroll/routes/payroll_routes.py
import os
import json
import uuid
import sqlite3
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

from payroll.engine import run_payroll

# ✅ Unique blueprint name (prevents "already registered" errors)
payroll_bp = Blueprint("payroll_api_v1", __name__, url_prefix="/payroll")

# ✅ Zero-new-deps persistence (SQLite)
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
                results_json TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


_init_db()


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
    results = run_payroll(contractors)

    run_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    # Persist payload + results
    conn = _db()
    try:
        conn.execute(
            """
            INSERT INTO payroll_runs (run_id, created_at, payload_json, results_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                run_id,
                created_at,
                json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
                json.dumps({"results": results}, separators=(",", ":"), ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"run_id": run_id, "created_at": created_at, "results": results}), 200


@payroll_bp.route("/runs/<run_id>", methods=["GET"])
def payroll_get_run(run_id: str):
    conn = _db()
    try:
        row = conn.execute(
            "SELECT run_id, created_at, payload_json, results_json FROM payroll_runs WHERE run_id = ?",
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
            "SELECT run_id, created_at FROM payroll_runs ORDER BY created_at DESC LIMIT ?",
            (limit_i,),
        ).fetchall()
    finally:
        conn.close()

    return jsonify({"runs": [{"run_id": r["run_id"], "created_at": r["created_at"]} for r in rows]}), 200

# legal/routes/legal_routes.py
import os
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

# Versioning (bump when you update policies)
TOS_VERSION = os.getenv("TOS_VERSION", "v1.0")
PRIVACY_VERSION = os.getenv("PRIVACY_VERSION", "v1.0")
REFUND_VERSION = os.getenv("REFUND_VERSION", "v1.0")

legal_bp = Blueprint("legal_api_v1", __name__, url_prefix="/legal")


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


@legal_bp.route("/versions", methods=["GET"])
def legal_versions():
    return jsonify(
        {
            "tos_version": TOS_VERSION,
            "privacy_version": PRIVACY_VERSION,
            "refund_version": REFUND_VERSION,
        }
    ), 200


@legal_bp.route("/accept", methods=["POST"])
def accept_legal():
    """
    Expected JSON:
    {
      "user_id": "123",
      "accept_tos": true,
      "accept_privacy": true,
      "accept_refund": true
    }
    """
    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")
    accept_tos = bool(data.get("accept_tos"))
    accept_privacy = bool(data.get("accept_privacy"))
    accept_refund = bool(data.get("accept_refund"))

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    if not (accept_tos and accept_privacy and accept_refund):
        return jsonify({"error": "All legal policies must be accepted"}), 400

    # Minimal persistence (SQLite) without adding deps:
    # If you are using Postgres already, your dev can move this to your existing DB layer.
    import sqlite3

    db_path = os.getenv("LEGAL_DB_PATH", "/tmp/legal.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS legal_acceptances (
                user_id TEXT PRIMARY KEY,
                tos_version TEXT NOT NULL,
                privacy_version TEXT NOT NULL,
                refund_version TEXT NOT NULL,
                accepted_at TEXT NOT NULL,
                accepted_ip TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO legal_acceptances (
                user_id, tos_version, privacy_version, refund_version, accepted_at, accepted_ip
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                tos_version=excluded.tos_version,
                privacy_version=excluded.privacy_version,
                refund_version=excluded.refund_version,
                accepted_at=excluded.accepted_at,
                accepted_ip=excluded.accepted_ip
            """,
            (
                str(user_id),
                TOS_VERSION,
                PRIVACY_VERSION,
                REFUND_VERSION,
                _now_iso(),
                request.headers.get("X-Forwarded-For") or request.remote_addr,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify(
        {
            "user_id": str(user_id),
            "tos_version": TOS_VERSION,
            "privacy_version": PRIVACY_VERSION,
            "refund_version": REFUND_VERSION,
            "accepted_at": _now_iso(),
        }
    ), 200


@legal_bp.route("/status/<user_id>", methods=["GET"])
def legal_status(user_id: str):
    import sqlite3

    db_path = os.getenv("LEGAL_DB_PATH", "/tmp/legal.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS legal_acceptances (
                user_id TEXT PRIMARY KEY,
                tos_version TEXT NOT NULL,
                privacy_version TEXT NOT NULL,
                refund_version TEXT NOT NULL,
                accepted_at TEXT NOT NULL,
                accepted_ip TEXT
            )
            """
        )
        row = conn.execute(
            """
            SELECT user_id, tos_version, privacy_version, refund_version, accepted_at, accepted_ip
            FROM legal_acceptances
            WHERE user_id = ?
            """,
            (str(user_id),),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify(
            {
                "user_id": str(user_id),
                "accepted": False,
                "required": {
                    "tos_version": TOS_VERSION,
                    "privacy_version": PRIVACY_VERSION,
                    "refund_version": REFUND_VERSION,
                },
            }
        ), 200

    accepted = (
        row["tos_version"] == TOS_VERSION
        and row["privacy_version"] == PRIVACY_VERSION
        and row["refund_version"] == REFUND_VERSION
    )

    return jsonify(
        {
            "user_id": row["user_id"],
            "accepted": bool(accepted),
            "accepted_at": row["accepted_at"],
            "accepted_ip": row["accepted_ip"],
            "versions": {
                "tos_version": row["tos_version"],
                "privacy_version": row["privacy_version"],
                "refund_version": row["refund_version"],
            },
            "required": {
                "tos_version": TOS_VERSION,
                "privacy_version": PRIVACY_VERSION,
                "refund_version": REFUND_VERSION,
            },
        }
    ), 200

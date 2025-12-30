# freightpay/bookkeeping/routes.py

from flask import Blueprint, jsonify, request
from datetime import datetime

from bookkeeping.ledger import (
    get_ledger,
    clear_ledger_db,   # MUST be DB-backed, transactional
)
from auth.decorators import require_admin
from utils.logger import audit_log

bookkeeping_bp = Blueprint("bookkeeping", __name__)

@bookkeeping_bp.get("/api/bookkeeping/ledger")
@require_admin
def api_get_ledger():
    return jsonify({
        "ledger": get_ledger()
    }), 200


@bookkeeping_bp.post("/api/bookkeeping/ledger/clear")
@require_admin
def api_clear_ledger():
    payload = request.get_json(force=True) or {}

    if payload.get("confirm") is not True:
        return jsonify({
            "error": 'Set {"confirm": true} to clear ledger'
        }), 400

    reason = payload.get("reason", "manual_clear")

    clear_ledger_db()

    audit_log(
        action="ledger_clear",
        details={
            "reason": reason,
            "ip": request.remote_addr,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

    return jsonify({
        "status": "cleared"
    }), 200

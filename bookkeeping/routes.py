# Freightpay/bookkeeping/routes.py

from flask import Blueprint, jsonify, request
from bookkeeping.ledger import get_ledger, clear_ledger

bookkeeping_bp = Blueprint("bookkeeping", __name__)

@bookkeeping_bp.get("/api/bookkeeping/ledger")
def api_get_ledger():
    return jsonify({"ledger": get_ledger()})

@bookkeeping_bp.post("api/bookkeeping/ledger/clear")
def api_clear_ledger():
    # simple safety: require a tiny confirmation flag
    payload = request.get_json(force=True) or {}
    if payload.get("confirm") is not True:
        return jsonify({"error": "Set {\"confirm\": true} to clear ledger"}), 400
      clear_ledger()
      return jsonify({"status": "cleared"})

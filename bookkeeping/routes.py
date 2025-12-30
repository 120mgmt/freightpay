# bookkeeping/routes.py

from flask import Blueprint, jsonify, request
from bookkeeping.ledger import (
    get_ledger,
    clear_ledger,
    record_payroll_run,
)

bookkeeping_bp = Blueprint("bookkeeping", __name__, url_prefix="/api/bookkeeping")


@bookkeeping_bp.get("/ledger")
def api_get_ledger():
    return jsonify({"ledger": get_ledger()}), 200


@bookkeeping_bp.post("/ledger/record")
def api_record_payroll():
    payload = request.get_json(force=True) or {}

    required = [
        "pay_period",
        "contractor_id",
        "gross",
        "reimbursements",
        "deductions",
        "net",
    ]
    missing = [k for k in required if k not in payload]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    entry = record_payroll_run(
        pay_period=payload["pay_period"],
        contractor_id=payload["contractor_id"],
        gross=payload["gross"],
        reimbursements=payload["reimbursements"],
        deductions=payload["deductions"],
        net=payload["net"],
    )

    return jsonify({"entry": entry}), 201


@bookkeeping_bp.post("/ledger/clear")
def api_clear_ledger():
    payload = request.get_json(force=True) or {}
    if payload.get("confirm") is not True:
        return (
            jsonify(
                {
                    "error": 'Set {"confirm": true} in request body to clear ledger'
                }
            ),
            400,
        )

    clear_ledger()
    return jsonify({"status": "cleared"}), 200

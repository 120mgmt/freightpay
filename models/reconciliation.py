# freightpay/routes/reconciliation.py
# FULL FILE — reconciliation endpoints (statement + match + finalize)

from datetime import datetime, date
from decimal import Decimal

from flask import Blueprint, request, jsonify

from freightpay.db import db
from freightpay.models.reconciliation import (
    BankStatement,
    BankStatementLine,
    ReconciliationStatus,
)
from freightpay.services.reconciliation import (
    match_statement_lines,
    finalize_reconciliation,
)
from freightpay.models.periods import AccountingPeriod

reconciliation_bp = Blueprint("reconciliation_bp", __name__, url_prefix="/reconciliation")


def _require_company_id() -> int:
    cid = request.headers.get("X-Company-Id") or (request.json or {}).get("company_id")
    if not cid:
        raise ValueError("Missing company_id")
    return int(cid)


# =========================
# PART 1 — IMPORT STATEMENT
# =========================
@reconciliation_bp.route("/statement", methods=["POST"])
def import_statement():
    try:
        company_id = _require_company_id()
        data = request.json or {}

        stmt = BankStatement(
            company_id=company_id,
            account_code=data["account_code"],
            period=data["period"],
            statement_start=date.fromisoformat(data["statement_start"]),
            statement_end=date.fromisoformat(data["statement_end"]),
            ending_balance=Decimal(data["ending_balance"]),
        )
        db.session.add(stmt)
        db.session.flush()

        for l in data.get("lines", []):
            db.session.add(
                BankStatementLine(
                    statement_id=stmt.id,
                    txn_date=date.fromisoformat(l["txn_date"]),
                    description=l["description"],
                    amount=Decimal(l["amount"]),
                )
            )

        db.session.commit()
        return jsonify({"statement_id": stmt.id}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


# =========================
# OPTIONAL — AUTO MATCH
# =========================
@reconciliation_bp.route("/match", methods=["POST"])
def auto_match():
    try:
        data = request.json or {}
        match_statement_lines(statement_id=int(data["statement_id"]))
        return jsonify({"matched": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# =========================
# PART 2 — FINALIZE
# =========================
@reconciliation_bp.route("/finalize", methods=["POST"])
def finalize():
    try:
        company_id = _require_company_id()
        data = request.json or {}

        rec = finalize_reconciliation(
            company_id=company_id,
            account_code=data["account_code"],
            period=data["period"],
        )

        return jsonify(
            {
                "company_id": str(company_id),
                "account_code": rec.account_code,
                "period": rec.period,
                "is_reconciled": rec.is_reconciled,
                "ledger_balance": str(rec.ledger_balance),
                "statement_balance": str(rec.statement_balance),
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400

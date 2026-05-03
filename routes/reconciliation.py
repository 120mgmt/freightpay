# routes/reconciliation.py
# FULL FILE — reconciliation endpoints (statement + match + finalize) — exports reconciliation_bp

from datetime import date
from decimal import Decimal

from flask import Blueprint, request, jsonify

from db import db
from models.reconciliation import BankStatement, BankStatementLine
from services.reconciliation import match_statement_lines, finalize_reconciliation

# ✅ Export name matches app.py: from routes.reconciliation import reconciliation_bp
reconciliation_bp = Blueprint("reconciliation_bp", __name__, url_prefix="/reconciliation")


def _require_company_id() -> int:
    cid = request.headers.get("X-Company-Id") or (request.json or {}).get("company_id")
    if not cid or not str(cid).strip():
        raise ValueError("Missing company_id")
    return int(str(cid).strip())


@reconciliation_bp.route("/statement", methods=["POST"])
def import_statement():
    try:
        company_id = _require_company_id()
        data = request.json or {}

        required = ["account_code", "period", "statement_start", "statement_end", "ending_balance"]
        for k in required:
            if k not in data or data[k] in (None, ""):
                raise ValueError(f"Missing required field: {k}")

        stmt = BankStatement(
            company_id=company_id,
            account_code=str(data["account_code"]).strip(),
            period=str(data["period"]).strip(),
            statement_start=date.fromisoformat(str(data["statement_start"])),
            statement_end=date.fromisoformat(str(data["statement_end"])),
            ending_balance=Decimal(str(data["ending_balance"])),
        )

        db.session.add(stmt)
        db.session.flush()

        for l in data.get("lines", []) or []:
            line_required = ["txn_date", "description", "amount"]
            for k in line_required:
                if k not in l or l[k] in (None, ""):
                    raise ValueError(f"Missing statement line field: {k}")

            db.session.add(
                BankStatementLine(
                    statement_id=stmt.id,
                    txn_date=date.fromisoformat(str(l["txn_date"])),
                    description=str(l["description"]).strip(),
                    amount=Decimal(str(l["amount"])),
                )
            )

        db.session.commit()
        return jsonify({"statement_id": stmt.id}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@reconciliation_bp.route("/match", methods=["POST"])
def auto_match():
    try:
        data = request.json or {}
        if "statement_id" not in data or data["statement_id"] in (None, ""):
            raise ValueError("Missing statement_id")
        match_statement_lines(statement_id=int(data["statement_id"]))
        return jsonify({"matched": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@reconciliation_bp.route("/finalize", methods=["POST"])
def finalize():
    try:
        company_id = _require_company_id()
        data = request.json or {}

        if not data.get("account_code"):
            raise ValueError("Missing account_code")
        if not data.get("period"):
            raise ValueError("Missing period")

        rec = finalize_reconciliation(
            company_id=company_id,
            account_code=str(data["account_code"]).strip(),
            period=str(data["period"]).strip(),
        )

        return jsonify(
            {
                "company_id": str(company_id),
                "account_code": rec.account_code,
                "period": rec.period,
                "is_reconciled": bool(rec.is_reconciled),
                "ledger_balance": str(rec.ledger_balance),
                "statement_balance": str(rec.statement_balance),
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400

# routes/coa.py
# FULL FILE — COA endpoints (seed + list)

from __future__ import annotations

from flask import Blueprint, request, jsonify

from db import db
from models.chart_of_accounts import Account
from services.coa import seed_default_coa

coa_bp = Blueprint("coa_bp", __name__, url_prefix="/coa")


def _require_company_id() -> str:
    cid = (
        request.headers.get("X-Company-Id")
        or request.args.get("company_id")
        or (request.json or {}).get("company_id")
    )
    if not cid or not str(cid).strip():
        raise ValueError("Missing company_id")
    return str(cid).strip()


@coa_bp.route("/seed", methods=["POST"])
def seed():
    try:
        company_id = _require_company_id()
        result = seed_default_coa(db.session, company_id=company_id)
        db.session.commit()
        return jsonify(result), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@coa_bp.route("/accounts", methods=["GET"])
def list_accounts():
    try:
        company_id = _require_company_id()
        rows = (
            db.session.query(Account)
            .filter(Account.company_id == company_id, Account.is_active.is_(True))
            .order_by(Account.account_code.asc())
            .all()
        )
        return jsonify(
            {
                "company_id": str(company_id),
                "count": len(rows),
                "accounts": [a.as_dict() if hasattr(a, "as_dict") else {
                    "id": str(a.id),
                    "company_id": str(a.company_id),
                    "account_code": a.account_code,
                    "name": a.name,
                    "account_type": a.account_type,
                    "normal_balance": a.normal_balance,
                    "parent_id": str(a.parent_id) if getattr(a, "parent_id", None) else None,
                    "is_active": a.is_active,
                    "is_system": a.is_system,
                } for a in rows],
            }
        ), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

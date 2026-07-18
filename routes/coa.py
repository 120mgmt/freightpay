# File: routes/coa.py
# Purpose: Chart of Accounts API routes (company-scoped, migration-safe)
# Status: Production-ready (crash-resistant imports, strict company_id parsing)
# Date: 2026-02-14

from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from db import db
from models.chart_of_accounts import ACCOUNT_TYPES, Account

coa_bp = Blueprint("coa_bp", __name__, url_prefix="/coa")

# An account's normal balance is implied by its type (standard accounting):
# assets & expenses increase on the debit side; the rest on the credit side.
_NORMAL_BALANCE_BY_TYPE = {
    "asset": "debit",
    "expense": "debit",
    "liability": "credit",
    "equity": "credit",
    "revenue": "credit",
}


def _require_company_id() -> int:
    cid = request.headers.get("X-Company-Id")
    if cid is None or str(cid).strip() == "":
        cid = request.args.get("company_id")

    if cid is None or str(cid).strip() == "":
        data = request.get_json(silent=True) or {}
        cid = data.get("company_id") if isinstance(data, dict) else None

    if cid is None or str(cid).strip() == "":
        raise ValueError("company_id_required")

    try:
        v = int(str(cid).strip())
        if v <= 0:
            raise ValueError("company_id_required")
        return v
    except Exception:
        raise ValueError("company_id_required")


@coa_bp.route("/seed", methods=["POST"])
def seed_coa():
    try:
        company_id = _require_company_id()

        # Lazy import to avoid app boot crash if service layer changes during deploys
        from services.coa import seed_default_coa  # type: ignore

        result = seed_default_coa(db.session, company_id=company_id)
        return jsonify(result), 200
    except ValueError:
        return jsonify({"error": "company_id_required"}), 400
    except Exception as e:
        return jsonify({"error": "seed_failed", "detail": str(e)}), 500


@coa_bp.route("/accounts", methods=["GET"])
def list_accounts():
    try:
        company_id = _require_company_id()
        stmt = (
            select(Account)
            .where(Account.company_id == company_id)
            .order_by(Account.account_code.asc(), Account.id.asc())
        )
        accounts = list(db.session.execute(stmt).scalars().all())
        return jsonify([a.as_dict() for a in accounts]), 200
    except ValueError:
        return jsonify({"error": "company_id_required"}), 400
    except Exception as e:
        return jsonify({"error": "list_failed", "detail": str(e)}), 500


@coa_bp.route("/accounts", methods=["POST"])
def create_account():
    """
    Add a single custom account to the company's chart of accounts.

    Body: {"account_code": "6100", "name": "Fuel", "account_type": "expense"}
    normal_balance is derived from account_type automatically.
    """
    try:
        company_id = _require_company_id()
    except ValueError:
        return jsonify({"error": "company_id_required"}), 400

    data = request.get_json(silent=True) or {}
    code = str(data.get("account_code") or "").strip()
    name = str(data.get("name") or "").strip()
    acct_type = str(data.get("account_type") or "").strip().lower()

    if not code:
        return jsonify({"error": "account_code_required"}), 400
    if not name:
        return jsonify({"error": "name_required"}), 400
    if acct_type not in ACCOUNT_TYPES:
        return jsonify({"error": "invalid_account_type", "allowed": list(ACCOUNT_TYPES)}), 400
    if len(code) > 50 or len(name) > 120:
        return jsonify({"error": "field_too_long"}), 400

    # Reject duplicates up front for a clean message (a DB unique constraint
    # also guards this at the company+code level).
    existing = db.session.execute(
        select(Account).where(
            Account.company_id == company_id,
            Account.account_code == code,
        )
    ).scalar_one_or_none()
    if existing:
        return jsonify({"error": "account_code_exists", "detail": f"Account code {code} already exists."}), 409

    account = Account(
        company_id=company_id,
        account_code=code,
        name=name,
        account_type=acct_type,
        normal_balance=_NORMAL_BALANCE_BY_TYPE[acct_type],
        is_system=False,
        is_active=True,
    )
    try:
        db.session.add(account)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "create_failed", "detail": str(e)}), 500

    return jsonify(account.as_dict()), 201


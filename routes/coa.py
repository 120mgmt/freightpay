# File: routes/coa.py
# Purpose: Chart of Accounts API routes (company-scoped, migration-safe)
# Status: Production-ready (crash-resistant imports, strict company_id parsing)
# Date: 2026-02-14

from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from db import db
from models.chart_of_accounts import Account

coa_bp = Blueprint("coa_bp", __name__, url_prefix="/coa")


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


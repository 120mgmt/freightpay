# freightpay/routes/reporting.py
# REPORTING ROUTES — exposes ledger-based TB / P&L / BS / Cash Flow

from __future__ import annotations

from flask import Blueprint, request, jsonify

from freightpay.db import db
from freightpay.services.reporting import (
    trial_balance,
    profit_and_loss,
    balance_sheet,
    cash_flow,
    financials,
)

reporting_bp = Blueprint("reporting_bp", __name__, url_prefix="/reports")


def _require_company_id() -> str:
    """
    Production-safe, explicit company scoping.
    Accepts:
      - Header: X-Company-Id
      - Query:  company_id
      - JSON:   company_id
    """
    cid = (
        request.headers.get("X-Company-Id")
        or request.args.get("company_id")
        or (request.json or {}).get("company_id")
    )
    if not cid or not str(cid).strip():
        raise ValueError("Missing company_id (X-Company-Id header or company_id param)")
    return str(cid).strip()


def _require_period_range() -> tuple[str, str]:
    data = request.json or {}
    period_from = (data.get("period_from") or request.args.get("period_from") or "").strip()
    period_to = (data.get("period_to") or request.args.get("period_to") or "").strip()

    if not period_from or not period_to:
        raise ValueError("Missing period_from or period_to")

    # format validation kept strict: YYYY-MM
    if len(period_from) != 7 or len(period_to) != 7 or period_from[4] != "-" or period_to[4] != "-":
        raise ValueError("period_from/period_to must be in YYYY-MM format")

    if period_from > period_to:
        raise ValueError("period_from cannot be after period_to")

    return period_from, period_to


@reporting_bp.route("/trial-balance", methods=["POST", "GET"])
def api_trial_balance():
    try:
        company_id = _require_company_id()
        period_from, period_to = _require_period_range()
        out = trial_balance(db.session, company_id=company_id, period_from=period_from, period_to=period_to)
        return jsonify(out), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@reporting_bp.route("/profit-and-loss", methods=["POST", "GET"])
def api_profit_and_loss():
    try:
        company_id = _require_company_id()
        period_from, period_to = _require_period_range()
        out = profit_and_loss(db.session, company_id=company_id, period_from=period_from, period_to=period_to)
        return jsonify(out), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@reporting_bp.route("/balance-sheet", methods=["POST", "GET"])
def api_balance_sheet():
    try:
        company_id = _require_company_id()
        period_from, period_to = _require_period_range()
        out = balance_sheet(db.session, company_id=company_id, period_from=period_from, period_to=period_to)
        return jsonify(out), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@reporting_bp.route("/cash-flow", methods=["POST", "GET"])
def api_cash_flow():
    try:
        company_id = _require_company_id()
        period_from, period_to = _require_period_range()
        out = cash_flow(db.session, company_id=company_id, period_from=period_from, period_to=period_to)
        return jsonify(out), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@reporting_bp.route("/financials", methods=["POST", "GET"])
def api_financials():
    try:
        company_id = _require_company_id()
        period_from, period_to = _require_period_range()
        out = financials(db.session, company_id=company_id, period_from=period_from, period_to=period_to)
        return jsonify(out), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

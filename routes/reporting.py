# routes/reporting.py
# FULL FILE — corrected so app.py can import reporting_bp

from __future__ import annotations

from flask import Blueprint, request, jsonify

from db import db
from services.reporting import (
    trial_balance,
    profit_and_loss,
    balance_sheet,
    cash_flow,
    financials,
)

# 🔧 FIX: blueprint name exported as reporting_bp
reporting_bp = Blueprint("reporting_bp", __name__, url_prefix="/reports")


def _require_company_id() -> str:
    cid = (
        request.headers.get("X-Company-Id")
        or request.args.get("company_id")
        or (request.json or {}).get("company_id")
    )
    if not cid or not str(cid).strip():
        raise ValueError("Missing company_id")
    return str(cid).strip()


def _require_period_range() -> tuple[str, str]:
    data = request.json or {}
    period_from = (data.get("period_from") or request.args.get("period_from") or "").strip()
    period_to = (data.get("period_to") or request.args.get("period_to") or "").strip()

    if not period_from or not period_to:
        raise ValueError("Missing period_from or period_to")

    if len(period_from) != 7 or len(period_to) != 7 or period_from[4] != "-" or period_to[4] != "-":
        raise ValueError("period_from/period_to must be YYYY-MM")

    if period_from > period_to:
        raise ValueError("period_from cannot be after period_to")

    return period_from, period_to


@reporting_bp.route("/trial-balance", methods=["GET", "POST"])
def api_trial_balance():
    try:
        company_id = _require_company_id()
        period_from, period_to = _require_period_range()
        return jsonify(
            trial_balance(
                db.session,
                company_id=company_id,
                period_from=period_from,
                period_to=period_to,
            )
        ), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@reporting_bp.route("/profit-and-loss", methods=["GET", "POST"])
def api_profit_and_loss():
    try:
        company_id = _require_company_id()
        period_from, period_to = _require_period_range()
        return jsonify(
            profit_and_loss(
                db.session,
                company_id=company_id,
                period_from=period_from,
                period_to=period_to,
            )
        ), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@reporting_bp.route("/balance-sheet", methods=["GET", "POST"])
def api_balance_sheet():
    try:
        company_id = _require_company_id()
        period_from, period_to = _require_period_range()
        return jsonify(
            balance_sheet(
                db.session,
                company_id=company_id,
                period_from=period_from,
                period_to=period_to,
            )
        ), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@reporting_bp.route("/cash-flow", methods=["GET", "POST"])
def api_cash_flow():
    try:
        company_id = _require_company_id()
        period_from, period_to = _require_period_range()
        return jsonify(
            cash_flow(
                db.session,
                company_id=company_id,
                period_from=period_from,
                period_to=period_to,
            )
        ), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@reporting_bp.route("/financials", methods=["GET", "POST"])
def api_financials():
    try:
        company_id = _require_company_id()
        period_from, period_to = _require_period_range()
        return jsonify(
            financials(
                db.session,
                company_id=company_id,
                period_from=period_from,
                period_to=period_to,
            )
        ), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
 
       
      
  

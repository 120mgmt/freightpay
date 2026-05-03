# File: routes/pricing_cpm.py
# Purpose: CPM config + evaluation routes (JWT enforced)
# Status: Production-ready
# Date: 2026-01-28

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from services.pricing_cpm import CPMInputs, compute_cpm
from services.pricing_cpm_repo import get_cpm_config, upsert_cpm_config


pricing_cpm_bp = Blueprint("pricing_cpm", __name__, url_prefix="/pricing/cpm")


def _identity() -> Dict[str, Any]:
    ident = get_jwt_identity() or {}
    if not isinstance(ident, dict):
        raise ValueError("Invalid JWT identity")
    if "company_id" not in ident or "role" not in ident:
        raise ValueError("JWT missing company_id/role")
    return ident


def _require_company_scope(target_company_id: int) -> Dict[str, Any]:
    ident = _identity()
    if int(ident["company_id"]) != int(target_company_id):
        raise ValueError("company_id mismatch")
    return ident


def _require_role(ident: Dict[str, Any], allowed: set[str]) -> None:
    role = str(ident.get("role", "")).strip().lower()
    if role not in allowed:
        raise ValueError("insufficient role")


def _d(v: Any) -> Decimal:
    return Decimal(str(v))


@pricing_cpm_bp.get("/config")
@jwt_required()
def get_config():
    try:
        company_id = int(request.args.get("company_id"))
        _require_company_scope(company_id)

        cfg = get_cpm_config(company_id)
        return jsonify({"company_id": company_id, "config": cfg}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@pricing_cpm_bp.put("/config")
@jwt_required()
def put_config():
    try:
        payload = request.get_json(force=True) or {}
        company_id = int(payload.get("company_id"))

        ident = _require_company_scope(company_id)
        _require_role(ident, allowed={"owner", "admin"})

        cfg = upsert_cpm_config(company_id, payload)
        return jsonify({"company_id": company_id, "config": cfg}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@pricing_cpm_bp.post("/evaluate")
@jwt_required()
def evaluate():
    try:
        payload = request.get_json(force=True) or {}
        company_id = int(payload["company_id"])

        ident = _require_company_scope(company_id)
        _require_role(ident, allowed={"owner", "admin", "dispatcher"})

        cfg = get_cpm_config(company_id)
        if not cfg:
            raise ValueError("CPM config not set for company")

        trip_miles = payload.get("trip_miles")
        offered_rate_total = payload.get("offered_rate_total")
        offered_rate_per_mile = payload.get("offered_rate_per_mile")

        if trip_miles is None:
            raise ValueError("trip_miles is required")
        if offered_rate_total is None and offered_rate_per_mile is None:
            raise ValueError("Provide offered_rate_total or offered_rate_per_mile")

        inputs = CPMInputs(
            fixed_monthly_costs=_d(cfg["fixed_monthly_costs"]),
            expected_monthly_miles=_d(cfg["expected_monthly_miles"]),
            maintenance_cpm=_d(cfg.get("maintenance_cpm", 0)),
            tolls_cpm=_d(cfg.get("tolls_cpm", 0)),
            driver_cpm=_d(cfg.get("driver_cpm", 0)),
            other_variable_cpm=_d(cfg.get("other_variable_cpm", 0)),
            profit_margin_pct=_d(cfg.get("profit_margin_pct", Decimal("0.20"))),
            fuel_price_per_gal=_d(cfg["fuel_price_per_gallon"]) if cfg.get("fuel_price_per_gallon") is not None else None,
            mpg=_d(cfg["mpg"]) if cfg.get("mpg") is not None else None,
            offered_rate_total=_d(offered_rate_total) if offered_rate_total is not None else None,
            offered_rate_per_mile=_d(offered_rate_per_mile) if offered_rate_per_mile is not None else None,
            trip_miles=_d(trip_miles),
        )

        result = compute_cpm(inputs)

        out = {
            "company_id": company_id,
            "fixed_cpm": str(result.fixed_cpm),
            "variable_cpm": str(result.variable_cpm),
            "breakeven_cpm": str(result.breakeven_cpm),
            "target_cpm": str(result.target_cpm),
            "profit_margin_pct": str(result.profit_margin_pct),
            "offered_cpm": (str(result.offered_cpm) if result.offered_cpm is not None else None),
            "decision": result.decision,
            "floor_rate_total": (str(result.floor_rate_total) if result.floor_rate_total is not None else None),
        }

        # Hard block on reject (profit floor)
        if result.decision == "reject":
            return jsonify(out), 422

        return jsonify(out), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

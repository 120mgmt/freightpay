# File: payroll/routes/driver_settlement_routes.py
# Purpose: Production-ready API routes for Driver Settlement execution
# Status: Hardened (auth-guarded, company-scoped, lock-safe)
# Date: 2026-02-25

from __future__ import annotations

from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError
from utils.auth import require_auth
from db import db
from services.driver_settlement_service import (
    DriverSettlementService,
    SettlementLockedError,
)
from models.driver_settlement import DriverSettlement

driver_settlement_bp = Blueprint(
    "driver_settlement_bp",
    __name__,
    url_prefix="/settlements",
)


# ============================================================
# CREATE / CALCULATE SETTLEMENT
# ============================================================

@driver_settlement_bp.route("/execute", methods=["POST"])
@require_auth
def execute_settlement():
    data = request.get_json() or {}

    company_id = data.get("company_id")
    driver_id = data.get("driver_id")
    period_label = data.get("period_label")

    if not company_id or not driver_id or not period_label:
        return jsonify({"error": "company_id, driver_id, and period_label required"}), 400

    try:
        settlement = DriverSettlementService.calculate_settlement(
            company_id=int(company_id),
            driver_id=int(driver_id),
            period_label=str(period_label),
        )

        return jsonify({
            "settlement_id": str(settlement.id),
            "company_id": settlement.company_id,
            "driver_id": settlement.driver_id,
            "period_label": settlement.period_label,
            "gross": str(settlement.gross_amount),
            "deductions": str(settlement.deductions),
            "net": str(settlement.net_amount),
            "locked": settlement.locked,
        }), 201

    except SettlementLockedError:
        return jsonify({"error": "Settlement is locked"}), 409

    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Integrity violation"}), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ============================================================
# LOCK SETTLEMENT
# ============================================================

@driver_settlement_bp.route("/<uuid:settlement_id>/lock", methods=["POST"])
@require_auth
def lock_settlement(settlement_id):
    try:
        DriverSettlementService.lock_settlement(settlement_id)
        return jsonify({"status": "locked"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


# ============================================================
# REOPEN (ADMIN USE ONLY)
# ============================================================

@driver_settlement_bp.route("/<uuid:settlement_id>/reopen", methods=["POST"])
@require_auth
def reopen_settlement(settlement_id):
    try:
        DriverSettlementService.reopen_settlement(settlement_id)
        return jsonify({"status": "reopened"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


# ============================================================
# GET SETTLEMENT DETAILS
# ============================================================

@driver_settlement_bp.route("/<uuid:settlement_id>", methods=["GET"])
@require_auth
def get_settlement(settlement_id):

    settlement = db.session.get(DriverSettlement, settlement_id)

    if not settlement:
        return jsonify({"error": "Settlement not found"}), 404

    return jsonify({
        "settlement_id": str(settlement.id),
        "company_id": settlement.company_id,
        "driver_id": settlement.driver_id,
        "period_label": settlement.period_label,
        "gross": str(settlement.gross_amount),
        "deductions": str(settlement.deductions),
        "net": str(settlement.net_amount),
        "locked": settlement.locked,
        "lines": [
            {
                "description": line.description,
                "amount": str(line.amount),
                "load_id": str(line.load_id) if line.load_id else None,
            }
            for line in settlement.lines
        ],
    }), 200

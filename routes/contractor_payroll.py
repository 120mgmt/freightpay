from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import select
from sqlalchemy.orm import Session

from utils.database import get_db
from models.payroll import PayrollSettlement, PayrollAudit, PayrollEscrow


contractor_payroll_bp = Blueprint(
    "contractor_payroll",
    __name__,
    url_prefix="/contractor/payroll",
)


# ─────────────────────────────────────────────
# LIST SETTLEMENTS (CONTRACTOR VIEW)
# ─────────────────────────────────────────────

@contractor_payroll_bp.route("/settlements/<contractor_id>", methods=["GET"])
@jwt_required()
def list_settlements(contractor_id: str):
    identity = get_jwt_identity() or {}
    # Contractors can only view their own settlements; admins can view any
    if str(identity.get("contractor_id", "")) != str(contractor_id) and identity.get("role") != "admin":
        return jsonify({"error": "forbidden"}), 403
    db: Session = get_db()

    stmt = (
        select(PayrollSettlement)
        .where(PayrollSettlement.contractor_id == contractor_id)
        .order_by(PayrollSettlement.period_end.desc())
    )
    settlements = db.execute(stmt).scalars().all()

    return jsonify([
        {
            "settlement_id": s.id,
            "period_start": s.period_start.isoformat(),
            "period_end": s.period_end.isoformat(),
            "pay_type": s.pay_type,
            "rate": str(s.rate),
            "units": str(s.units),
            "gross": str(s.gross_amount),
            "adjusted_gross": str(s.adjusted_gross_amount),
            "net_pay": str(s.net_amount),
            "status": s.status,
        }
        for s in settlements
    ]), 200


# ─────────────────────────────────────────────
# VIEW SINGLE SETTLEMENT (DETAIL)
# ─────────────────────────────────────────────

@contractor_payroll_bp.route("/settlement/<settlement_id>", methods=["GET"])
@jwt_required()
def view_settlement(settlement_id: str):
    db: Session = get_db()

    settlement = db.get(PayrollSettlement, settlement_id)
    if not settlement:
        return jsonify({"error": "Settlement not found"}), 404

    return jsonify({
        "settlement_id": settlement.id,
        "period_start": settlement.period_start.isoformat(),
        "period_end": settlement.period_end.isoformat(),
        "pay_type": settlement.pay_type,
        "rate": str(settlement.rate),
        "units": str(settlement.units),
        "gross": str(settlement.gross_amount),
        "adjusted_gross": str(settlement.adjusted_gross_amount),
        "net_pay": str(settlement.net_amount),
        "status": settlement.status,
    }), 200


# ─────────────────────────────────────────────
# ESCROW BALANCE (READ ONLY)
# ─────────────────────────────────────────────

@contractor_payroll_bp.route("/escrow/<contractor_id>", methods=["GET"])
@jwt_required()
def escrow_balance(contractor_id: str):
    identity = get_jwt_identity() or {}
    if str(identity.get("contractor_id", "")) != str(contractor_id) and identity.get("role") != "admin":
        return jsonify({"error": "forbidden"}), 403
    db: Session = get_db()

    stmt = select(PayrollEscrow).where(PayrollEscrow.contractor_id == contractor_id)
    entries = list(db.execute(stmt).scalars().all())

    balance = 0
    for e in entries:
        if e.is_release:
            balance += float(e.amount)
        else:
            balance -= float(e.amount)

    return jsonify({
        "contractor_id": contractor_id,
        "escrow_balance": round(balance, 2),
    }), 200


# ─────────────────────────────────────────────
# AUDIT HISTORY (READ ONLY)
# ─────────────────────────────────────────────

@contractor_payroll_bp.route("/audit/<settlement_id>", methods=["GET"])
@jwt_required()
def audit_history(settlement_id: str):
    db: Session = get_db()

    stmt = (
        select(PayrollAudit)
        .where(PayrollAudit.settlement_id == settlement_id)
        .order_by(PayrollAudit.created_at.asc())
    )
    audits = list(db.execute(stmt).scalars().all())

    return jsonify([
        {
            "action": a.action,
            "actor": a.actor,
            "snapshot": a.snapshot,
            "created_at": a.created_at.isoformat(),
        }
        for a in audits
    ]), 200
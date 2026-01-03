from decimal import Decimal
from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session

from freightpay.db import get_db
from freightpay.services.payroll_service import (
    build_settlement,
    approve_settlement,
    void_existing_settlement,
    pay_settlement,
)
from freightpay.repositories.payroll_repository import (
    save_settlement,
    replace_accessorials,
    replace_deductions,
    write_audit,
    mark_settlement_status,
)


admin_payroll_bp = Blueprint("admin_payroll", __name__, url_prefix="/admin/payroll")


# ─────────────────────────────────────────────
# CREATE / UPDATE DRAFT SETTLEMENT
# ─────────────────────────────────────────────

@admin_payroll_bp.route("/settlement", methods=["POST"])
def create_or_update_settlement():
    data = request.json
    db: Session = get_db()

    settlement_id = data["settlement_id"]
    contractor_id = data["contractor_id"]

    result = build_settlement(
        settlement_id=settlement_id,
        contractor_id=contractor_id,
        status=data["status"],
        pay_type=data["pay_type"],
        rate=Decimal(str(data["rate"])),
        units=Decimal(str(data["units"])),
        revenue=Decimal(str(data["revenue"])) if data.get("revenue") else None,
        accessorials=data.get("accessorials", []),
        deductions=data.get("deductions", []),
        escrow_contribution=None,
        escrow_release=None,
        entitlement_active=data["entitlement_active"],
        exists_for_period=data["exists_for_period"],
    )

    settlement = save_settlement(
        db,
        settlement_id=settlement_id,
        contractor_id=contractor_id,
        period_start=data["period_start"],
        period_end=data["period_end"],
        pay_type=data["pay_type"],
        rate=Decimal(str(data["rate"])),
        units=Decimal(str(data["units"])),
        revenue=Decimal(str(data["revenue"])) if data.get("revenue") else None,
        snapshot=result["calculation_snapshot"],
    )

    replace_accessorials(
        db,
        settlement=settlement,
        accessorials=data.get("accessorials", []),
    )

    replace_deductions(
        db,
        settlement=settlement,
        deductions=data.get("deductions", []),
    )

    db.commit()

    return jsonify({
        "settlement_id": settlement.id,
        "status": settlement.status,
        "snapshot": result["calculation_snapshot"],
    }), 200


# ─────────────────────────────────────────────
# APPROVE SETTLEMENT
# ─────────────────────────────────────────────

@admin_payroll_bp.route("/settlement/approve", methods=["POST"])
def approve():
    data = request.json
    db: Session = get_db()

    audit = approve_settlement(
        settlement_id=data["settlement_id"],
        status=data["status"],
        calculation_snapshot=data["calculation_snapshot"],
        approved_by=data["approved_by"],
    )

    mark_settlement_status(
        db,
        settlement_id=data["settlement_id"],
        status="approved",
    )

    write_audit(
        db,
        settlement_id=data["settlement_id"],
        action="approved",
        actor=data["approved_by"],
        snapshot=data["calculation_snapshot"],
    )

    db.commit()
    return jsonify(audit), 200


# ─────────────────────────────────────────────
# VOID SETTLEMENT
# ─────────────────────────────────────────────

@admin_payroll_bp.route("/settlement/void", methods=["POST"])
def void():
    data = request.json
    db: Session = get_db()

    audit = void_existing_settlement(
        settlement_id=data["settlement_id"],
        status=data["status"],
        voided_by=data["voided_by"],
        reason=data["reason"],
    )

    mark_settlement_status(
        db,
        settlement_id=data["settlement_id"],
        status="voided",
    )

    write_audit(
        db,
        settlement_id=data["settlement_id"],
        action="voided",
        actor=data["voided_by"],
        snapshot=audit,
    )

    db.commit()
    return jsonify(audit), 200


# ─────────────────────────────────────────────
# MARK AS PAID
# ─────────────────────────────────────────────

@admin_payroll_bp.route("/settlement/pay", methods=["POST"])
def pay():
    data = request.json
    db: Session = get_db()

    audit = pay_settlement(
        settlement_id=data["settlement_id"],
        status=data["status"],
        paid_by=data["paid_by"],
        payout_reference=data["payout_reference"],
    )

    mark_settlement_status(
        db,
        settlement_id=data["settlement_id"],
        status="paid",
    )

    write_audit(
        db,
        settlement_id=data["settlement_id"],
        action="paid",
        actor=data["paid_by"],
        snapshot=audit,
    )

    db.commit()
    return jsonify(audit), 200

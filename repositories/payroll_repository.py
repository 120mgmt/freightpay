from typing import Dict, Any
from decimal import Decimal

from sqlalchemy import delete
from sqlalchemy.orm import Session

from models.payroll import (
    PayrollSettlement,
    PayrollAccessorial,
    PayrollDeduction,
    PayrollEscrow,
    PayrollAudit,
)


# ─────────────────────────────────────────────
# SETTLEMENT CREATE / UPDATE
# ─────────────────────────────────────────────

def save_settlement(
    db: Session,
    *,
    settlement_id: str,
    contractor_id: str,
    period_start,
    period_end,
    pay_type: str,
    rate: Decimal,
    units: Decimal,
    revenue: Decimal | None,
    snapshot: Dict[str, Any],
) -> PayrollSettlement:
    """
    Creates or updates a draft settlement.
    """

    settlement = db.get(PayrollSettlement, settlement_id)

    if not settlement:
        settlement = PayrollSettlement(
            id=settlement_id,
            contractor_id=contractor_id,
            period_start=period_start,
            period_end=period_end,
        )
        db.add(settlement)

    settlement.pay_type = pay_type
    settlement.rate = rate
    settlement.units = units
    settlement.revenue = revenue
    settlement.gross_amount = snapshot["gross"]
    settlement.adjusted_gross_amount = snapshot["adjusted_gross"]
    settlement.net_amount = snapshot["net_pay"]

    db.flush()
    return settlement


# ─────────────────────────────────────────────
# ACCESSORIALS
# ─────────────────────────────────────────────

def replace_accessorials(
    db: Session,
    *,
    settlement: PayrollSettlement,
    accessorials: list[Dict[str, Any]],
) -> None:
    db.execute(delete(PayrollAccessorial).where(PayrollAccessorial.settlement_id == settlement.id))

    for item in accessorials:
        db.add(
            PayrollAccessorial(
                settlement_id=settlement.id,
                type=item["type"],
                description=item.get("description"),
                amount=item["amount"],
            )
        )


# ─────────────────────────────────────────────
# DEDUCTIONS
# ─────────────────────────────────────────────

def replace_deductions(
    db: Session,
    *,
    settlement: PayrollSettlement,
    deductions: list[Dict[str, Any]],
) -> None:
    db.execute(delete(PayrollDeduction).where(PayrollDeduction.settlement_id == settlement.id))

    for item in deductions:
        db.add(
            PayrollDeduction(
                settlement_id=settlement.id,
                category=item["category"],
                description=item.get("description"),
                amount=item["amount"],
                recoverable=item.get("recoverable", False),
            )
        )


# ─────────────────────────────────────────────
# ESCROW ENTRIES
# ─────────────────────────────────────────────

def add_escrow_entry(
    db: Session,
    *,
    contractor_id: str,
    settlement_id: str | None,
    amount: Decimal,
    is_release: bool,
    approved_by: str | None = None,
) -> PayrollEscrow:
    entry = PayrollEscrow(
        contractor_id=contractor_id,
        settlement_id=settlement_id,
        amount=amount,
        is_release=is_release,
        approved_by=approved_by,
    )
    db.add(entry)
    db.flush()
    return entry


# ─────────────────────────────────────────────
# AUDIT LOGGING
# ─────────────────────────────────────────────

def write_audit(
    db: Session,
    *,
    settlement_id: str,
    action: str,
    actor: str,
    snapshot: Dict[str, Any],
) -> PayrollAudit:
    audit = PayrollAudit(
        settlement_id=settlement_id,
        action=action,
        actor=actor,
        snapshot=snapshot,
    )
    db.add(audit)
    db.flush()
    return audit


# ─────────────────────────────────────────────
# STATE TRANSITIONS
# ─────────────────────────────────────────────

def mark_settlement_status(
    db: Session,
    *,
    settlement_id: str,
    status: str,
) -> None:
    settlement = db.get(PayrollSettlement, settlement_id)
    if not settlement:
        raise ValueError("Settlement not found")

    settlement.status = status
    db.flush()

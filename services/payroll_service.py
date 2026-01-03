from decimal import Decimal
from typing import Dict, Any, List

from freightpay.payroll.calculations import calculate_settlement
from freightpay.payroll.validators import (
    validate_pay_type_and_units,
    validate_rate,
    validate_settlement_editable,
    validate_active_entitlement,
    validate_unique_settlement,
    validate_net_pay,
)
from freightpay.payroll.approvals import (
    lock_settlement,
    void_settlement,
    mark_as_paid,
)


# ─────────────────────────────────────────────
# SETTLEMENT CREATION / UPDATE
# ─────────────────────────────────────────────

def build_settlement(
    *,
    settlement_id: str,
    contractor_id: str,
    status: str,
    pay_type: str,
    rate: Decimal,
    units: Decimal,
    revenue: Decimal | None,
    accessorials: List[Dict[str, Decimal]],
    deductions: List[Dict[str, Decimal]],
    escrow_contribution: Decimal | None,
    escrow_release: Decimal | None,
    entitlement_active: bool,
    exists_for_period: bool,
    allow_negative_net: bool = False,
) -> Dict[str, Any]:
    """
    Builds a settlement calculation snapshot.
    Does NOT persist anything.
    """

    # HARD GATES
    validate_active_entitlement(entitlement_active)
    validate_unique_settlement(exists_for_period)
    validate_settlement_editable(status)
    validate_rate(rate)
    validate_pay_type_and_units(pay_type, units, revenue)

    # CALCULATION (single source)
    snapshot = calculate_settlement(
        pay_type=pay_type,
        rate=rate,
        units=units,
        revenue=revenue,
        accessorials=accessorials,
        deductions=deductions,
        escrow_contribution=escrow_contribution,
        escrow_release=escrow_release,
        allow_negative_net=allow_negative_net,
    )

    validate_net_pay(
        net_cents=int(snapshot["net_pay"] * 100),
        allow_negative=allow_negative_net,
    )

    return {
        "settlement_id": settlement_id,
        "contractor_id": contractor_id,
        "status": status,
        "calculation_snapshot": snapshot,
    }


# ─────────────────────────────────────────────
# APPROVAL
# ─────────────────────────────────────────────

def approve_settlement(
    *,
    settlement_id: str,
    status: str,
    calculation_snapshot: Dict[str, Any],
    approved_by: str,
) -> Dict[str, Any]:
    """
    Locks a settlement and returns audit data.
    """

    return lock_settlement(
        settlement_id=settlement_id,
        status=status,
        calculation_snapshot=calculation_snapshot,
        approved_by=approved_by,
    )


# ─────────────────────────────────────────────
# VOID
# ─────────────────────────────────────────────

def void_existing_settlement(
    *,
    settlement_id: str,
    status: str,
    voided_by: str,
    reason: str,
) -> Dict[str, Any]:
    """
    Voids an approved settlement.
    """

    return void_settlement(
        settlement_id=settlement_id,
        status=status,
        voided_by=voided_by,
        reason=reason,
    )


# ─────────────────────────────────────────────
# PAID
# ─────────────────────────────────────────────

def pay_settlement(
    *,
    settlement_id: str,
    status: str,
    paid_by: str,
    payout_reference: str,
) -> Dict[str, Any]:
    """
    Marks a settlement as paid.
    """

    return mark_as_paid(
        settlement_id=settlement_id,
        status=status,
        paid_by=paid_by,
        payout_reference=payout_reference,
    )

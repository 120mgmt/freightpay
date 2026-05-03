from datetime import datetime
from typing import Dict, Any


# ─────────────────────────────────────────────
# APPROVAL & LOCKING
# ─────────────────────────────────────────────

LOCKED_STATUSES = ("approved", "paid")


def validate_can_approve(status: str) -> None:
    """
    Ensures a settlement can be approved.
    """
    if status in LOCKED_STATUSES:
        raise ValueError("Settlement is already locked")


def lock_settlement(
    *,
    settlement_id: str,
    status: str,
    calculation_snapshot: Dict[str, Any],
    approved_by: str,
) -> Dict[str, Any]:
    """
    Locks a settlement and returns an immutable audit snapshot.
    This function does NOT persist data. Persistence is handled
    by the service layer.
    """

    validate_can_approve(status)

    if not calculation_snapshot:
        raise ValueError("Calculation snapshot is required for approval")

    audit_snapshot = {
        "settlement_id": settlement_id,
        "status": "approved",
        "approved_by": approved_by,
        "approved_at": datetime.utcnow().isoformat(),
        "calculation_snapshot": calculation_snapshot,
    }

    return audit_snapshot


# ─────────────────────────────────────────────
# VOIDING (CONTROLLED RESET)
# ─────────────────────────────────────────────

def validate_can_void(status: str) -> None:
    """
    Only approved (not paid) settlements may be voided.
    """
    if status != "approved":
        raise ValueError("Only approved settlements may be voided")


def void_settlement(
    *,
    settlement_id: str,
    status: str,
    voided_by: str,
    reason: str,
) -> Dict[str, Any]:
    """
    Voids a settlement. Requires recreation for changes.
    """

    validate_can_void(status)

    if not reason:
        raise ValueError("Void reason is required")

    return {
        "settlement_id": settlement_id,
        "status": "voided",
        "voided_by": voided_by,
        "voided_at": datetime.utcnow().isoformat(),
        "reason": reason,
    }


# ─────────────────────────────────────────────
# PAID STATE
# ─────────────────────────────────────────────

def mark_as_paid(
    *,
    settlement_id: str,
    status: str,
    paid_by: str,
    payout_reference: str,
) -> Dict[str, Any]:
    """
    Marks a settlement as paid.
    """

    if status != "approved":
        raise ValueError("Only approved settlements may be marked as paid")

    if not payout_reference:
        raise ValueError("Payout reference is required")

    return {
        "settlement_id": settlement_id,
        "status": "paid",
        "paid_by": paid_by,
        "paid_at": datetime.utcnow().isoformat(),
        "payout_reference": payout_reference,
    }

from decimal import Decimal
from typing import Literal


PayType = Literal["per_mile", "flat_rate", "percentage", "hourly"]


# ─────────────────────────────────────────────
# PAY TYPE + UNITS VALIDATION
# ─────────────────────────────────────────────

def validate_pay_type_and_units(
    pay_type: PayType,
    units: Decimal,
    revenue: Decimal | None = None,
) -> None:
    """
    Enforces correct unit usage per pay type.
    """

    if units < 0:
        raise ValueError("Units cannot be negative")

    if pay_type == "percentage":
        if revenue is None or revenue <= 0:
            raise ValueError("Revenue is required for percentage pay type")

    if pay_type in ("per_mile", "hourly") and units <= 0:
        raise ValueError("Units must be greater than zero")

    if pay_type == "flat_rate":
        # units are ignored but must be zero or one
        if units not in (Decimal("0"), Decimal("1")):
            raise ValueError("Flat rate pay type cannot have variable units")


# ─────────────────────────────────────────────
# RATE VALIDATION
# ─────────────────────────────────────────────

def validate_rate(rate: Decimal) -> None:
    if rate <= 0:
        raise ValueError("Rate must be greater than zero")


# ─────────────────────────────────────────────
# SETTLEMENT STATE VALIDATION
# ─────────────────────────────────────────────

def validate_settlement_editable(status: str) -> None:
    """
    Prevents edits once approved or paid.
    """
    if status in ("approved", "paid"):
        raise ValueError("Settlement is locked and cannot be edited")


# ─────────────────────────────────────────────
# ENTITLEMENT VALIDATION
# ─────────────────────────────────────────────

def validate_active_entitlement(is_active: bool) -> None:
    if not is_active:
        raise PermissionError("Active subscription required for payroll access")


# ─────────────────────────────────────────────
# NET PAY VALIDATION
# ─────────────────────────────────────────────

def validate_net_pay(net_cents: int, allow_negative: bool = False) -> None:
    if net_cents < 0 and not allow_negative:
        raise ValueError("Net pay cannot be negative")


# ─────────────────────────────────────────────
# PAY PERIOD DUPLICATION GATE
# ─────────────────────────────────────────────

def validate_unique_settlement(
    exists_for_period: bool,
) -> None:
    if exists_for_period:
        raise ValueError("Settlement already exists for this contractor and period")

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Literal


PayType = Literal["per_mile", "flat_rate", "percentage", "hourly"]


def _to_cents(amount: Decimal) -> int:
    """
    Convert a Decimal dollar amount to integer cents.
    """
    return int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _from_cents(cents: int) -> Decimal:
    """
    Convert integer cents back to Decimal dollars.
    """
    return (Decimal(cents) / Decimal("100")).quantize(Decimal("0.01"))


# ─────────────────────────────────────────────
# CORE GROSS PAY CALCULATION
# ─────────────────────────────────────────────

def calculate_gross(
    pay_type: PayType,
    rate: Decimal,
    units: Decimal,
    revenue: Decimal | None = None,
) -> int:
    """
    Returns gross pay in CENTS.
    """

    if pay_type == "per_mile":
        gross = units * rate

    elif pay_type == "flat_rate":
        gross = rate

    elif pay_type == "percentage":
        if revenue is None:
            raise ValueError("Revenue required for percentage pay type")
        gross = revenue * rate

    elif pay_type == "hourly":
        gross = units * rate

    else:
        raise ValueError(f"Unsupported pay type: {pay_type}")

    if gross < 0:
        raise ValueError("Gross pay cannot be negative")

    return _to_cents(gross)


# ─────────────────────────────────────────────
# ACCESSORIALS
# ─────────────────────────────────────────────

def apply_accessorials(
    gross_cents: int,
    accessorials: List[Dict[str, Decimal]],
) -> int:
    """
    Each accessorial dict requires:
    - amount: Decimal (positive or negative)
    """

    total = gross_cents

    for item in accessorials:
        amount = item.get("amount")
        if amount is None:
            raise ValueError("Accessorial missing amount")

        total += _to_cents(amount)

    return total


# ─────────────────────────────────────────────
# DEDUCTIONS
# ─────────────────────────────────────────────

def apply_deductions(
    adjusted_gross_cents: int,
    deductions: List[Dict[str, Decimal]],
    allow_negative_net: bool = False,
) -> int:
    """
    Each deduction dict requires:
    - amount: Decimal (positive number)
    """

    total_deductions = 0

    for item in deductions:
        amount = item.get("amount")
        if amount is None:
            raise ValueError("Deduction missing amount")
        if amount < 0:
            raise ValueError("Deduction amount cannot be negative")

        total_deductions += _to_cents(amount)

    net = adjusted_gross_cents - total_deductions

    if net < 0 and not allow_negative_net:
        raise ValueError("Net pay cannot be negative")

    return net


# ─────────────────────────────────────────────
# ESCROW
# ─────────────────────────────────────────────

def apply_escrow(
    net_cents: int,
    escrow_contribution: Decimal | None = None,
    escrow_release: Decimal | None = None,
) -> int:
    """
    Escrow contributions reduce net pay.
    Escrow releases increase net pay.
    """

    total = net_cents

    if escrow_contribution:
        if escrow_contribution < 0:
            raise ValueError("Escrow contribution cannot be negative")
        total -= _to_cents(escrow_contribution)

    if escrow_release:
        if escrow_release < 0:
            raise ValueError("Escrow release cannot be negative")
        total += _to_cents(escrow_release)

    return total


# ─────────────────────────────────────────────
# FULL SETTLEMENT CALCULATION (AUTHORITATIVE)
# ─────────────────────────────────────────────

def calculate_settlement(
    *,
    pay_type: PayType,
    rate: Decimal,
    units: Decimal,
    revenue: Decimal | None,
    accessorials: List[Dict[str, Decimal]],
    deductions: List[Dict[str, Decimal]],
    escrow_contribution: Decimal | None = None,
    escrow_release: Decimal | None = None,
    allow_negative_net: bool = False,
) -> Dict[str, Decimal]:
    """
    Returns a FULL calculation snapshot in dollars (Decimal).
    """

    gross_cents = calculate_gross(
        pay_type=pay_type,
        rate=rate,
        units=units,
        revenue=revenue,
    )

    adjusted_gross_cents = apply_accessorials(
        gross_cents=gross_cents,
        accessorials=accessorials,
    )

    net_before_escrow_cents = apply_deductions(
        adjusted_gross_cents=adjusted_gross_cents,
        deductions=deductions,
        allow_negative_net=allow_negative_net,
    )

    final_net_cents = apply_escrow(
        net_cents=net_before_escrow_cents,
        escrow_contribution=escrow_contribution,
        escrow_release=escrow_release,
    )

    if final_net_cents < 0 and not allow_negative_net:
        raise ValueError("Final net pay cannot be negative")

    return {
        "gross": _from_cents(gross_cents),
        "adjusted_gross": _from_cents(adjusted_gross_cents),
        "net_before_escrow": _from_cents(net_before_escrow_cents),
        "net_pay": _from_cents(final_net_cents),
    }

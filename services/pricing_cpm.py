from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional, Literal


Decision = Literal["approve", "review", "reject"]

TWOPLACES = Decimal("0.01")
FOURPLACES = Decimal("0.0001")


def _d(val) -> Decimal:
    """
    Convert input to Decimal safely using str(), avoiding float binary issues.
    Accepts: Decimal, int, str, float (converted via str()).
    """
    if val is None:
        raise ValueError("Numeric value is required")
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val).strip())
    except (InvalidOperation, ValueError, AttributeError):
        raise ValueError(f"Invalid numeric value: {val!r}") from None


def _d0(val) -> Decimal:
    """Optional numeric to Decimal; None -> 0."""
    if val is None:
        return Decimal("0")
    return _d(val)


def q_money(x: Decimal) -> Decimal:
    return x.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def q_cpm(x: Decimal) -> Decimal:
    return x.quantize(FOURPLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CPMInputs:
    # Fixed costs (monthly) and expected miles (monthly)
    fixed_monthly_costs: Decimal
    expected_monthly_miles: Decimal

    # Variable CPM components
    fuel_price_per_gal: Optional[Decimal] = None
    mpg: Optional[Decimal] = None
    maintenance_cpm: Decimal = Decimal("0")
    tolls_cpm: Decimal = Decimal("0")
    driver_cpm: Decimal = Decimal("0")
    other_variable_cpm: Decimal = Decimal("0")

    # Profit margin (0.20 = 20%)
    profit_margin_pct: Decimal = Decimal("0.20")

    # Offer (optional)
    offered_rate_total: Optional[Decimal] = None  # $ total
    offered_rate_per_mile: Optional[Decimal] = None  # $/mile
    trip_miles: Optional[Decimal] = None


@dataclass(frozen=True)
class CPMResult:
    fixed_cpm: Decimal
    variable_cpm: Decimal
    breakeven_cpm: Decimal
    target_cpm: Decimal
    offered_cpm: Optional[Decimal]
    decision: Decision
    floor_rate_total: Optional[Decimal]
    profit_margin_pct: Decimal


def compute_fuel_cpm(fuel_price_per_gal: Decimal, mpg: Decimal) -> Decimal:
    mpg = _d(mpg)
    if mpg <= 0:
        raise ValueError("mpg must be > 0")
    fuel_price_per_gal = _d(fuel_price_per_gal)
    if fuel_price_per_gal < 0:
        raise ValueError("fuel_price_per_gal cannot be negative")
    return fuel_price_per_gal / mpg


def compute_cpm(inputs: CPMInputs) -> CPMResult:
    fixed_monthly_costs = _d(inputs.fixed_monthly_costs)
    expected_monthly_miles = _d(inputs.expected_monthly_miles)

    if fixed_monthly_costs < 0:
        raise ValueError("fixed_monthly_costs cannot be negative")
    if expected_monthly_miles <= 0:
        raise ValueError("expected_monthly_miles must be > 0")

    # Fixed CPM
    fixed_cpm = fixed_monthly_costs / expected_monthly_miles

    # Variable CPM
    fuel_cpm = Decimal("0")
    if inputs.fuel_price_per_gal is not None or inputs.mpg is not None:
        if inputs.fuel_price_per_gal is None or inputs.mpg is None:
            raise ValueError("Provide both fuel_price_per_gal and mpg to compute fuel CPM")
        fuel_cpm = compute_fuel_cpm(_d(inputs.fuel_price_per_gal), _d(inputs.mpg))

    maintenance_cpm = _d0(inputs.maintenance_cpm)
    tolls_cpm = _d0(inputs.tolls_cpm)
    driver_cpm = _d0(inputs.driver_cpm)
    other_variable_cpm = _d0(inputs.other_variable_cpm)

    for name, v in (
        ("maintenance_cpm", maintenance_cpm),
        ("tolls_cpm", tolls_cpm),
        ("driver_cpm", driver_cpm),
        ("other_variable_cpm", other_variable_cpm),
    ):
        if v < 0:
            raise ValueError(f"{name} cannot be negative")

    variable_cpm = fuel_cpm + maintenance_cpm + tolls_cpm + driver_cpm + other_variable_cpm
    if variable_cpm < 0:
        raise ValueError("variable_cpm cannot be negative")

    breakeven_cpm = fixed_cpm + variable_cpm

    profit_margin_pct = _d(inputs.profit_margin_pct)
    if profit_margin_pct < 0:
        raise ValueError("profit_margin_pct cannot be negative")

    target_cpm = breakeven_cpm * (Decimal("1") + profit_margin_pct)

    # Offered CPM (optional)
    offered_cpm: Optional[Decimal] = None
    if inputs.offered_rate_per_mile is not None:
        offered_cpm = _d(inputs.offered_rate_per_mile)
        if offered_cpm < 0:
            raise ValueError("offered_rate_per_mile cannot be negative")
    elif inputs.offered_rate_total is not None and inputs.trip_miles is not None:
        offered_rate_total = _d(inputs.offered_rate_total)
        trip_miles = _d(inputs.trip_miles)
        if offered_rate_total < 0:
            raise ValueError("offered_rate_total cannot be negative")
        if trip_miles <= 0:
            raise ValueError("trip_miles must be > 0 when offered_rate_total is provided")
        offered_cpm = offered_rate_total / trip_miles

    # Floor total (optional)
    floor_rate_total: Optional[Decimal] = None
    if inputs.trip_miles is not None:
        trip_miles = _d(inputs.trip_miles)
        if trip_miles <= 0:
            raise ValueError("trip_miles must be > 0")
        floor_rate_total = target_cpm * trip_miles

    # Decision bands:
    # - reject: offered < target
    # - review: offered between target and target*1.05 (inclusive)
    # - approve: offered > target*1.05
    decision: Decision = "review"
    if offered_cpm is not None:
        if offered_cpm < target_cpm:
            decision = "reject"
        elif offered_cpm <= (target_cpm * Decimal("1.05")):
            decision = "review"
        else:
            decision = "approve"

    return CPMResult(
        fixed_cpm=q_cpm(fixed_cpm),
        variable_cpm=q_cpm(variable_cpm),
        breakeven_cpm=q_cpm(breakeven_cpm),
        target_cpm=q_cpm(target_cpm),
        offered_cpm=(q_cpm(offered_cpm) if offered_cpm is not None else None),
        decision=decision,
        floor_rate_total=(q_money(floor_rate_total) if floor_rate_total is not None else None),
        profit_margin_pct=profit_margin_pct,
    )

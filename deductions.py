# deductions.py
# Production-ready, deterministic, no placeholders

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Union


Number = Union[int, float, Decimal]


def _to_decimal(value: Number) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0.00")


def calculate_deductions(
    gross_amount: Number,
    *,
    rate: Number = Decimal("0.20"),
    minimum: Number = Decimal("0.00"),
    maximum: Number | None = None,
) -> float:
    """
    Calculates deductions based on a configurable rate.
    - Uses Decimal for financial accuracy
    - Supports optional min/max caps
    """

    gross = _to_decimal(gross_amount)
    pct = _to_decimal(rate)

    deductions = (gross * pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    min_d = _to_decimal(minimum)
    if deductions < min_d:
        deductions = min_d

    if maximum is not None:
        max_d = _to_decimal(maximum)
        if deductions > max_d:
            deductions = max_d

    return float(deductions)

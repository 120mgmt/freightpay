# contractor_pay.py
# Production-ready contractor net pay calculator

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Union

Number = Union[int, float, Decimal]


def calculate_contractor_pay(amount: Number, rate: Number = Decimal("0.90")) -> float:
    """
    Calculate contractor net pay.

    :param amount: Gross amount before contractor split
    :param rate: Contractor payout rate (default 90%)
    :return: Net contractor pay rounded to 2 decimals
    """
    gross = Decimal(str(amount))
    pct = Decimal(str(rate))

    if gross < 0:
        raise ValueError("amount must be >= 0")
    if pct <= 0 or pct > 1:
        raise ValueError("rate must be between 0 and 1")

    net = (gross * pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(net)

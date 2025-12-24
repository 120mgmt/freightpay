# payroll/accessorials.py
from __future__ import annotations

from typing import Any, Dict


def _f(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return float(default)
        return float(x)
    except (TypeError, ValueError):
        return float(default)


def compute_accessorials(earnings: Dict[str, Any] | None) -> Dict[str, float]:
    """
    Trucking accessorial earnings. These ADD to gross.

    Inputs expected inside `earnings`:
      detention_hours, detention_rate
      layover (flat)
      stops, stop_rate
      tonu (flat)
      breakdown_hours, breakdown_rate OR breakdown_flat
      bonuses (flat)
    """
    e = earnings or {}

    detention = _f(e.get("detention_hours")) * _f(e.get("detention_rate"))
    layover = _f(e.get("layover"))
    stop_pay = _f(e.get("stops")) * _f(e.get("stop_rate"))
    tonu = _f(e.get("tonu"))

    # breakdown: prefer hours*rate, but allow breakdown_flat
    breakdown_flat = _f(e.get("breakdown_flat"))
    breakdown = (_f(e.get("breakdown_hours")) * _f(e.get("breakdown_rate"))) + breakdown_flat

    bonuses = _f(e.get("bonuses"))

    total = detention + layover + stop_pay + tonu + breakdown + bonuses

    return {
        "detention": detention,
        "layover": layover,
        "stop_pay": stop_pay,
        "tonu": tonu,
        "breakdown": breakdown,
        "bonuses": bonuses,
        "total_accessorials": total,
    }
>

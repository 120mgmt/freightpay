# payroll/accessorials.py
from __future__ import annotations

from typing import Any, Dict

__all__ = ["compute_accessorials"]


def _to_float(value: Any, default: float = 0.0) -> float:
    """
    Best-effort numeric coercion.
    Accepts int/float/str (e.g., "12", "12.5"); returns default on None/invalid.
    """
    if value is None:
        return float(default)
    try:
        if isinstance(value, str):
            v = value.strip()
            if v == "":
                return float(default)
            return float(v)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def compute_accessorials(data: Dict[str, Any] | None) -> Dict[str, float]:
    """
    Compute standard trucking accessorial earnings.

    Expected keys (all optional):
      - detention_hours, detention_rate  -> detention = hours * rate
      - layover                          -> layover flat
      - stops, stop_rate                 -> stop_pay = stops * rate
      - tonu                             -> tonu flat
      - breakdown_hours, breakdown_rate   -> breakdown_hours * breakdown_rate
      - breakdown_flat                   -> optional flat breakdown add-on
      - bonuses                          -> bonuses flat

    Returns per-line amounts + total.
    """
    e: Dict[str, Any] = data or {}

    detention = _to_float(e.get("detention_hours")) * _to_float(e.get("detention_rate"))
    layover = _to_float(e.get("layover"))
    stop_pay = _to_float(e.get("stops")) * _to_float(e.get("stop_rate"))
    tonu = _to_float(e.get("tonu"))

    breakdown = (
        _to_float(e.get("breakdown_hours")) * _to_float(e.get("breakdown_rate"))
        + _to_float(e.get("breakdown_flat"))
    )

    bonuses = _to_float(e.get("bonuses"))

    total = detention + layover + stop_pay + tonu + breakdown + bonuses

    return {
        "detention": detention,
        "layover": layover,
        "stop_pay": stop_pay,
        "tonu": tonu,
        "breakdown": breakdown,
        "bonuses": bonuses,
        "total": total,
    }

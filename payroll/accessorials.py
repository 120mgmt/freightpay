
Ashley Ross <info@120mgmt.com>
1:29 AM (0 minutes ago)
to me

# payroll/accessorials.py
from __future__ import annotations

from typing import Any, Dict

__all__ = [
    "compute_accessorials",
    "compute_earnings",        # backward compatibility
    "compute_reimbursements",  # future-proof
    "compute_deductions",      # future-proof
]


def _to_float(value: Any, default: float = 0.0) -> float:
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


# === ACCESSORIAL / EARNINGS ===
def compute_accessorials(data: Dict[str, Any] | None) -> Dict[str, float]:
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


# === ALIASES (ENGINE SAFETY) ===
def compute_earnings(data: Dict[str, Any] | None) -> Dict[str, float]:
    return compute_accessorials(data)


def compute_reimbursements(data: Dict[str, Any] | None) -> Dict[str, float]:
    # Placeholder for fuel, tolls, per diem, etc.
    return {}


def compute_deductions(data: Dict[str, Any] | None) -> Dict[str, float]:
    # Placeholder for escrow, advances, chargebacks
    return {}

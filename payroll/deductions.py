# payroll/deductions.py
from __future__ import annotations

from typing import Any, Dict


def _f(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return float(default)
        return float(x)
    except (TypeError, ValueError):
        return float(default)


def compute_deductions(d: Dict[str, Any] | None) -> Dict[str, float]:
    """
    Deductions that reduce pay. All fields are optional.
    """
    d = d or {}

    admin_fee = _f(d.get("admin_fee"))
    advances = _f(d.get("advances"))
    chargebacks = _f(d.get("chargebacks"))
    equipment = _f(d.get("equipment"))
    escrow = _f(d.get("escrow"))
    insurance = _f(d.get("insurance"))
    other = _f(d.get("other"))

    total = admin_fee + advances + chargebacks + equipment + escrow + insurance + other

    return {
        "admin_fee": admin_fee,
        "advances": advances,
        "chargebacks": chargebacks,
        "equipment": equipment,
        "escrow": escrow,
        "insurance": insurance,
        "other": other,
        "total_deductions": total,
    }

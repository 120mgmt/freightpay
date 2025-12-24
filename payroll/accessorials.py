# payroll/accessorials.py
from __future__ import annotations

from typing import Any, Dict


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


def compute_earnings(earnings: Dict[str, Any] | None) -> Dict[str, float]:
    """
    Earnings add to taxable gross (unless you later separate taxable/non-taxable).
    Standard trucking earnings:
      - detention (hours * rate)
      - layover (flat)
      - stop_pay (stops * rate)
      - tonu (flat)
      - breakdown (hours * rate) + optional breakdown_flat
      - bonuses (flat)
    """
    e: Dict[str, Any] = earnings or {}

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


def compute_reimbursements(reimbursements: Dict[str, Any] | None) -> Dict[str, float]:
    """
    Reimbursements are typically non-taxable (policy-dependent).
    Common buckets:
      - fuel
      - tolls
      - lumper
      - parking
      - other
    """
    r: Dict[str, Any] = reimbursements or {}

    fuel = _to_float(r.get("fuel"))
    tolls = _to_float(r.get("tolls"))
    lumper = _to_float(r.get("lumper"))
    parking = _to_float(r.get("parking"))
    other = _to_float(r.get("other"))

    total = fuel + tolls + lumper + parking + other

    return {
        "fuel": fuel,
        "tolls": tolls,
        "lumper": lumper,
        "parking": parking,
        "other": other,
        "total": total,
    }


def compute_deductions(deductions: Dict[str, Any] | None) -> Dict[str, float]:
    """
    Deductions reduce net pay.
    Common buckets:
      - admin_fee
      - advances
      - chargebacks
      - equipment
      - escrow
      - other
    """
    d: Dict[str, Any] = deductions or {}

    admin_fee = _to_float(d.get("admin_fee"))
    advances = _to_float(d.get("advances"))
    chargebacks = _to_float(d.get("chargebacks"))
    equipment = _to_float(d.get("equipment"))
    escrow = _to_float(d.get("escrow"))
    other = _to_float(d.get("other"))

    total = admin_fee + advances + chargebacks + equipment + escrow + other

    return {
        "admin_fee": admin_fee,
        "advances": advances,
        "chargebacks": chargebacks,
        "equipment": equipment,
        "escrow": escrow,
        "other": other,
        "total": total,
    }

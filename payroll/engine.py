# payroll/engine.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple, Union

from payroll.accessorials import compute_accessorials
from payroll.deductions import compute_deductions

__all__ = ["run_payroll"]


def _f(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return float(default)
        return float(x)
    except (TypeError, ValueError):
        return float(default)


def _s(x: Any, default: str = "") -> str:
    return default if x is None else str(x)


def compute_base_gross(contractor: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """
    Base pay supports:
      - pay_type "mile": miles * rate_per_mile
      - pay_type "flat": flat_amount
      - pay_type "hour": hours * hourly_rate
      - pay_type "percent": revenue * percent_rate  (e.g., 0.25 = 25%)
    """
    pay_type = _s(contractor.get("pay_type"), "mile").lower()

    if pay_type == "flat":
        base = _f(contractor.get("flat_amount"))
        detail = {"pay_type": "flat", "flat_amount": base}

    elif pay_type == "hour":
        hours = _f(contractor.get("hours"))
        rate = _f(contractor.get("hourly_rate"))
        base = hours * rate
        detail = {"pay_type": "hour", "hours": hours, "hourly_rate": rate}

    elif pay_type == "percent":
        revenue = _f(contractor.get("revenue"))
        pct = _f(contractor.get("percent_rate"))
        base = revenue * pct
        detail = {"pay_type": "percent", "revenue": revenue, "percent_rate": pct}

    else:  # default mile
        miles = _f(contractor.get("miles"))
        rpm = _f(contractor.get("rate_per_mile"))
        base = miles * rpm
        detail = {"pay_type": "mile", "miles": miles, "rate_per_mile": rpm}

    return base, detail


def run_payroll(payload: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Dict[str, Any]:
    """
    Accepts either:
      - payload dict: {"contractors":[...]}
      - contractors list directly: [...]
    Returns: {"results":[...], "totals": {...}}
    """

    # Fix #1 (from your logs): handle list payloads so we never call .get on a list
    if isinstance(payload, list):
        contractors: List[Dict[str, Any]] = payload
    else:
        contractors = payload.get("contractors") or []
        if not isinstance(contractors, list):
            return {"error": "Missing/invalid 'contractors' (must be a list)."}

    results: List[Dict[str, Any]] = []

    totals: Dict[str, float] = {
        "base_gross_total": 0.0,
        "accessorials_total": 0.0,
        "deductions_total": 0.0,
        "net_total": 0.0,
    }

    for c in contractors:
        if not isinstance(c, dict):
            continue

        contractor_id = c.get("id")

        base_gross, base_detail = compute_base_gross(c)

        access = compute_accessorials(c.get("accessorials"))
        # Fix #2 (from your logs): accessorials uses key "total", not "total_accessorials"
        access_total = _f(access.get("total", 0.0))

        deductions = compute_deductions(c.get("deductions"))
        deductions_total = _f(deductions.get("total", 0.0))

        gross = base_gross + access_total
        net = gross - deductions_total

        totals["base_gross_total"] += base_gross
        totals["accessorials_total"] += access_total
        totals["deductions_total"] += deductions_total
        totals["net_total"] += net

        results.append(
            {
                "contractor_id": contractor_id,
                "base_gross": base_gross,
                "base_detail": base_detail,
                "accessorials": access,
                "deductions": deductions,
                "gross": gross,
                "net": net,
            }
        )

    return {"results": results, "totals": totals}

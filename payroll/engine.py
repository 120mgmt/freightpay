# payroll/engine.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple, Union

from payroll.accessorials import compute_accessorials
from payroll.deductions import compute_deductions


def _f(x: Any, default: float = 0.0) -> float:
    """Best-effort float conversion (handles None/empty/invalid)."""
    try:
        if x is None:
            return float(default)
        if isinstance(x, str):
            s = x.strip()
            if s == "":
                return float(default)
            return float(s)
        return float(x)
    except (TypeError, ValueError):
        return float(default)


def _s(x: Any, default: str = "") -> str:
    return default if x is None else str(x)


def compute_base_gross(contractor: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """
    Base pay logic (before accessorials/deductions).

    Supports:
      - pay_type="mile"       -> miles * rate_per_mile
      - pay_type="hourly"     -> hours * hourly_rate
      - pay_type="percentage" -> load_gross * percent (accepts 30 or 0.30)
      - pay_type="flat"       -> flat_amount
      - weekly_guarantee      -> tops up base_gross if base is below guarantee
    """
    pay_type = _s(contractor.get("pay_type"), "mile").lower()

    miles = _f(contractor.get("miles"))
    rate_per_mile = _f(contractor.get("rate_per_mile"))

    hours = _f(contractor.get("hours"))
    hourly_rate = _f(contractor.get("hourly_rate"))

    flat_amount = _f(contractor.get("flat_amount"))

    load_gross = _f(contractor.get("load_gross"))
    percent = _f(contractor.get("percent")) or _f(contractor.get("percentage"))

    base = 0.0
    detail: Dict[str, Any] = {"pay_type": pay_type}

    if pay_type == "mile":
        base = miles * rate_per_mile
        detail.update({"miles": miles, "rate_per_mile": rate_per_mile})
    elif pay_type == "hourly":
        base = hours * hourly_rate
        detail.update({"hours": hours, "hourly_rate": hourly_rate})
    elif pay_type == "percentage":
        # Accept 30 (meaning 30%) or 0.30 (meaning 30%)
        pct = percent / 100.0 if percent > 1.0 else percent
        base = load_gross * pct
        detail.update({"load_gross": load_gross, "percent": pct})
    elif pay_type == "flat":
        base = flat_amount
        detail.update({"flat_amount": flat_amount})
    else:
        # Safe fallback: treat unknown pay_type as flat
        base = flat_amount
        detail.update({"flat_amount": flat_amount, "fallback": True})

    weekly_guarantee = _f(contractor.get("weekly_guarantee"))
    guarantee_topup = 0.0
    if weekly_guarantee > 0 and base < weekly_guarantee:
        guarantee_topup = weekly_guarantee - base
        base = weekly_guarantee

    detail.update(
        {
            "weekly_guarantee": weekly_guarantee,
            "guarantee_topup": guarantee_topup,
            "base_gross": base,
        }
    )
    return base, detail


def run_payroll(payload: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Dict[str, Any]:
    """
    Accepts either:
      1) {"contractors": [ ... ]}  (preferred)
      2) [ ... ]                  (raw list fallback)

    Returns:
      {
        "results": [...],
        "totals": {
          "base_gross_total": ...,
          "accessorials_total": ...,
          "deductions_total": ...,
          "net_total": ...
        }
      }
    """
    contractors: List[Dict[str, Any]]
    if isinstance(payload, list):
        contractors = payload
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
        # accessorials module returns key "total"
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

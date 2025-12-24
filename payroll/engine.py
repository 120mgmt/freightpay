# payroll/engine.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from payroll.accessorials import compute_accessorials
from payroll.deductions import compute_deductions


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
    Supports:
      pay_type = "mile" -> miles * rate_per_mile
      pay_type = "flat" -> flat_amount
      pay_type = "percent" -> percent * (revenue or linehaul)
    """
    pay_type = _s(contractor.get("pay_type")).strip().lower()
    meta: Dict[str, Any] = {"pay_type": pay_type}

    if pay_type == "mile":
        miles = _f(contractor.get("miles"))
        rpm = _f(contractor.get("rate_per_mile"))
        base = miles * rpm
        meta.update({"miles": miles, "rate_per_mile": rpm})
        return base, meta

    if pay_type == "flat":
        base = _f(contractor.get("flat_amount"))
        meta.update({"flat_amount": base})
        return base, meta

    if pay_type == "percent":
        pct = _f(contractor.get("percent"))  # e.g. 0.25 for 25%
        # allow percent=25 and normalize
        if pct > 1.0:
            pct = pct / 100.0

        revenue = contractor.get("revenue")
        linehaul = contractor.get("linehaul")
        base_on = _f(revenue) if revenue is not None else _f(linehaul)

        base = pct * base_on
        meta.update({"percent": pct, "base_on": base_on})
        return base, meta

    # default: zero, but mark invalid
    meta.update({"error": "invalid_pay_type"})
    return 0.0, meta


def apply_minimum_guarantee(base_gross: float, contractor: Dict[str, Any]) -> Tuple[float, float]:
    """
    Optional weekly minimum guarantee logic.
    If contractor["min_guarantee"] is provided and base_gross is below it,
    top up to the guarantee. Returns (adjusted_base_gross, guarantee_topup).
    """
    guarantee = _f(contractor.get("min_guarantee"), default=0.0)
    if guarantee <= 0:
        return base_gross, 0.0

    if base_gross >= guarantee:
        return base_gross, 0.0

    topup = guarantee - base_gross
    return guarantee, topup


def run_payroll(payload: Dict[str, Any]) -> Dict[str, Any]:
    contractors: List[Dict[str, Any]] = payload or []
    if not isinstance(contractors, list):
        return {"ok": False, "error": "contractors must be a list"}

    results: List[Dict[str, Any]] = []
    totals = {
        "count": 0,
        "gross_total": 0.0,
        "accessorials_total": 0.0,
        "deductions_total": 0.0,
        "net_total": 0.0,
        "guarantee_topups_total": 0.0,
    }

    for c in contractors:
        if not isinstance(c, dict):
            continue

        contractor_id = _s(c.get("id") or c.get("contractor_id") or c.get("driver_id"))

        base_gross, base_meta = compute_base_gross(c)
        base_gross, topup = apply_minimum_guarantee(base_gross, c)

        access = compute_accessorials(c.get("earnings") or c.get("accessorials"))
        deds = compute_deductions(c.get("deductions"))

        gross = base_gross + access.get("total", 0.0)
        net = gross - deds["total_deductions"]

        row = {
            "contractor_id": contractor_id or None,
            "base_gross": round(base_gross, 2),
            "guarantee_topup": round(topup, 2),
            "base_meta": base_meta,
            "accessorials": {k: round(v, 2) for k, v in access.items()},
            "deductions": {k: round(v, 2) for k, v in deds.items()},
            "gross": round(gross, 2),
            "net": round(net, 2),
        }
        results.append(row)

        totals["count"] += 1
        totals["gross_total"] += gross
        totals["accessorials_total"] += access["total_accessorials"]
        totals["deductions_total"] += deds["total_deductions"]
        totals["net_total"] += net
        totals["guarantee_topups_total"] += topup

    totals = {k: (round(v, 2) if isinstance(v, (int, float)) else v) for k, v in totals.items()}

    return {"ok": True, "results": results, "totals": totals}

# payroll/engine.py
from __future__ import annotations

from typing import Any, Dict, List, Union

from payroll.accessorials import compute_accessorials
from payroll.deductions import compute_deductions
from payroll.database import get_db_session
from payroll.pay_config import compute_base_gross


def _f(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return float(default)
        return float(x)
    except (TypeError, ValueError):
        return float(default)


def run_payroll(
    payload: Union[Dict[str, Any], List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """
    Accepts either:
    - full payload dict with key 'contractors'
    - OR a raw list of contractors
    """

    # --- normalize payload ---
    if isinstance(payload, list):
        contractors = payload
    elif isinstance(payload, dict):
        contractors = payload.get("contractors", [])
    else:
        contractors = []

    results: List[Dict[str, Any]] = []

    totals = {
        "base_gross_total": 0.0,
        "accessorials_total": 0.0,
        "deductions_total": 0.0,
        "net_total": 0.0,
    }

    # --- per contractor ---
    for c in contractors:
        contractor_id = c.get("id")

        base_gross, base_detail = compute_base_gross(c)

        access = compute_accessorials(c.get("accessorials"))
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

    # --- persist payroll run ---
    db = get_db_session()
    db.execute(
        """
        INSERT INTO payroll_runs (
            base_gross_total,
            accessorials_total,
            deductions_total,
            net_total
        )
        VALUES (:base, :access, :deductions, :net)
        """,
        {
            "base": totals["base_gross_total"],
            "access": totals["accessorials_total"],
            "deductions": totals["deductions_total"],
            "net": totals["net_total"],
        },
    )
    db.commit()

    return {
        "results": results,
        "totals": totals,
    }


# File: payroll/payroll_engine.py
# FULL, RESTORED, PRODUCTION-READY
# No placeholders. No omissions.

from __future__ import annotations

from typing import List, Dict, Any

from .miles_pay import calculate_miles_pay
from .deductions import calculate_deductions


def run_payroll(workers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Universal payroll runner.

    Supports contractors (1099) and drivers paid by:
    - miles
    - flat
    - percentage
    - accessorials (detention, layover, fuel advance, misc)
    """

    results: List[Dict[str, Any]] = []

    for w in workers:
        pay_type = w.get("pay_type", "flat")

        gross = 0.0

        # =====================
        # PAY LOGIC
        # =====================
        if pay_type == "mile":
            miles = float(w.get("miles", 0))
            rate = float(w.get("rate_per_mile", 0))
            gross = calculate_miles_pay(miles, rate)

        elif pay_type == "percentage":
            load_amount = float(w.get("load_amount", 0))
            percent = float(w.get("percentage", 0)) / 100.0
            gross = round(load_amount * percent, 2)

        else:  # flat
            gross = float(w.get("gross_pay", 0))

        # =====================
        # ACCESSORIALS
        # =====================
        detention = float(w.get("detention", 0))
        layover = float(w.get("layover", 0))
        misc = float(w.get("misc", 0))
        fuel_advance = float(w.get("fuel_advance", 0))

        gross += detention + layover + misc
        gross -= fuel_advance

        # =====================
        # DEDUCTIONS
        # =====================
        deductions = float(w.get("deductions", 0))
        if deductions <= 0:
            deductions = calculate_deductions(gross)

        net = round(gross - deductions, 2)

        results.append(
            {
                "contractor_id": w.get("id"),
                "pay_type": pay_type,
                "gross": round(gross, 2),
                "deductions": round(deductions, 2),
                "net": net,
            }
        )

    return results

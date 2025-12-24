# freightpay/payroll/engine.py

from .miles_pay import calculate_miles_pay
from .accessorials import (
    compute_earnings,
    compute_reimbursements,
    compute_deductions
)

def _f(x, default=0.0) -> float:
    try:
        if x is None or x == "":
            return float(default)
        return float(x)
    except (TypeError, ValueError):
        return float(default)


def run_payroll(contractors):
    """
    Production payroll engine (trucking focused)

    contractors = [
        {
            "contractor_id": "123",
            "pay_type": "mile" | "flat",
            "miles": 1200,
            "rate_per_mile": 0.65,
            "gross_pay": 2500,
            "earnings": {...},
            "reimbursements": {...},
            "deductions": {...}
        }
    ]
    """

    results = []
    contractors = contractors or []

    for c in contractors:
        pay_type = (c.get("pay_type") or "flat").lower()

        # 1) Base gross
        if pay_type == "mile":
            miles = _f(c.get("miles"))
            rate = _f(c.get("rate_per_mile"))
            base_gross = calculate_miles_pay(miles, rate)
        else:
            base_gross = _f(c.get("gross_pay"))

        # 2) Accessorial earnings (taxable)
        earnings_breakdown = compute_earnings(c.get("earnings") or {})
        earnings_total = _f(earnings_breakdown.get("total_earnings_accessorials"))
        taxable_gross = round(base_gross + earnings_total, 2)

        # 3) Reimbursements (non-taxable)
        reimburse_breakdown = compute_reimbursements(c.get("reimbursements") or {})
        reimburse_total = _f(reimburse_breakdown.get("total_reimbursements"))

        # 4) Deductions
        deductions_breakdown = compute_deductions(
            c.get("deductions") or {},
            taxable_gross
        )
        deductions_total = _f(deductions_breakdown.get("total_deductions"))

        # 5) Net
        net = round(taxable_gross - deductions_total + reimburse_total, 2)

        results.append({
            "contractor_id": c.get("contractor_id"),
            "pay_type": pay_type,
            "base_gross": round(base_gross, 2),
            "taxable_gross": taxable_gross,
            "earnings": earnings_breakdown,
            "reimbursements": reimburse_breakdown,
            "deductions": deductions_breakdown,
            "net_pay": net
        })

    return {
        "status": "ok",
        "count": len(results),
        "results": results
    }
     

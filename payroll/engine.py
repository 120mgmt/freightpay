from .miles_pay import calculate_miles_pay
from .deductions import calculate_deductions
from payroll.miles_pay import calculate_miles_pay
from payroll.accessorials import compute_earnings, compute_reimbursements, compute_deductions

def run_payroll(contractors):
    results = []

    for c in contractors or []:
        contractor_id = c.get("id") or c.get("contractor_id") or ""
        pay_type = (c.get("pay_type") or "mile").lower()

        # 1) Base miles/flat earnings
        gross_miles = 0.0
        if pay_type == "mile":
            miles = c.get("miles", 0)
            rpm = c.get("rate_per_mile", 0)
            gross_miles = calculate_miles_pay(miles, rpm)
        elif pay_type == "flat":
            gross_miles = round(float(c.get("flat_amount", 0) or 0), 2)

        # 2) Accessorial earnings (detention/layover/stop/tonu/breakdown/bonuses)
        earnings_breakdown = compute_earnings(c.get("earnings") or {})
        gross_accessorials = earnings_breakdown["total_earnings_accessorials"]

        # 3) Taxable gross (what deductions % should apply to)
        taxable_gross = round(gross_miles + gross_accessorials, 2)

        # 4) Minimum weekly guarantee (optional)
        guarantee = c.get("minimum_guarantee")
        if guarantee is not None:
            g = round(float(guarantee), 2)
            if taxable_gross < g:
                # add difference as "guarantee top-up"
                top_up = round(g - taxable_gross, 2)
                gross_accessorials = round(gross_accessorials + top_up, 2)
                taxable_gross = g
                earnings_breakdown["minimum_guarantee_top_up"] = top_up
                earnings_breakdown["total_earnings_accessorials"] = round(
                    earnings_breakdown["total_earnings_accessorials"] + top_up, 2
                )

        # 5) Team split (optional)
        team_split = c.get("team_split")
        if team_split is not None:
            split = float(team_split)
            if split > 1:
                split = split / 100.0
            split = max(0.0, min(split, 1.0))
            taxable_gross = round(taxable_gross * split, 2)
            gross_miles = round(gross_miles * split, 2)
            gross_accessorials = round(gross_accessorials * split, 2)
            earnings_breakdown["team_split"] = split

        # 6) Reimbursements (paid on top of net)
        reimburse_breakdown = compute_reimbursements(c.get("reimbursements") or {})
        reimburse_total = reimburse_breakdown["total_reimbursements"]

        # 7) Deductions (percent, fuel advance, escrow, etc.)
        deductions_breakdown = compute_deductions(c.get("deductions") or {}, taxable_gross)
        deductions_total = deductions_breakdown["total_deductions"]

        # 8) Net pay = taxable gross - deductions + reimbursements
        net_pay = round(taxable_gross - deductions_total + reimburse_total, 2)

        results.append({
            "contractor_id": contractor_id,
            "pay_type": pay_type,
            "gross_miles": gross_miles,
            "gross_accessorials": gross_accessorials,
            "taxable_gross": taxable_gross,
            "reimbursements_total": reimburse_total,
            "deductions_total": deductions_total,
            "net_pay": net_pay,
            "earnings_breakdown": earnings_breakdown,
            "reimbursements_breakdown": reimburse_breakdown,
            "deductions_breakdown": deductions_breakdown,
        })

    return results


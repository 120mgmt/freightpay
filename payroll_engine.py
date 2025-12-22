from .miles_pay import calculate_miles_pay
from .deductions import calculate_deductions

def run_payroll(contractors):
    results = []

    for c in contractors:
        pay_type = c.get("pay_type", "flat")  # "mile" or "flat"

        if pay_type == "mile":
            miles = float(c.get("miles", 0))
            rate = float(c.get("rate_per_mile", 0))
            gross = calculate_miles_pay(miles, rate)
        else:
            gross = float(c.get("gross_pay", 0))

        deductions = float(c.get("deductions", 0))
        if deductions == 0:
            deductions = float(calculate_deductions(gross))

        net = round(gross - deductions, 2)

        results.append({
            "contractor_id": c.get("id"),
            "pay_type": pay_type,
            "gross": gross,
            "deductions": deductions,
            "net": net
        })

    return results

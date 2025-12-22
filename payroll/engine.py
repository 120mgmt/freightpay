def run_payroll(contractors):
    results = []
    for c in contractors
        gross = c.get("gross_pay", 0)
        deductions = c.get("deductions", 0)
        net = gross - deductions

        results.append({
            "contractor_id": c.get("id"),
            "gross": gross,
            "deductions": deductions,
            "net": net
        })
      return results


def run_payroll(data):
    gross = data.get("gross", 0)
    deductions = data.get("deductions", 0)
    net = gross - deductions
    return {
        "gross": gross,
        "deductions": deductions,
        "net": net
    }

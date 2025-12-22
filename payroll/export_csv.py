import csv
import io
def settlements_to_csv(results):
    """
    results = list of dicts (like what run_payroll returnd
    returns CSV text
    """
    output = io.StringIO()
    writer = csv.writer(output)

# Header
writer.writerow(["contractor_id", "pay_type", "gross", "deductions", "net"])

# Rows
for r in results or []:
    writer.writerow([
        r.get("contractor_id", ""),
        r.get("pay_type", "")
        r.get("gross", 0)
        r.get("deductions", 0),
        r.get("net", 0),
    ])
    return output.getvalue()

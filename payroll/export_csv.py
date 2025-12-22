import csv
import io

def settlements_to_csv(results):
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "contractor_id",
        "pay_type",
        "gross_miles",
        "gross_accessorials",
        "taxable_gross",
        "reimbursements_total",
        "deductions_total",
        "net_pay"
    ])

    for r in results or []:
        writer.writerow([
            r.get("contractor_id", ""),
            r.get("pay_type", ""),
            r.get("gross_miles", 0),
            r.get("gross_accessorials", 0),
            r.get("taxable_gross", 0),
            r.get("reimbursements_total", 0),
            r.get("deductions_total", 0),
            r.get("net_pay", 0),
        ])

    return output.getvalue()

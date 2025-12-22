# payroll/export_csv.py

import csv
import io

def settlements_to_csv(results):
    output = io.StringIO()
    writer = csv.writer(output)

    # HEADER
    writer.writerow([
        "contractor_id",
        "pay_type",
        "gross",
        "accessorials",
        "deductions",
        "net"
    ])

    # ROWS
    for r in results:
        writer.writerow([
            r.get("contractor_id", ""),
            r.get("pay_type", ""),
            r.get("gross", 0),
            r.get("accessorials", 0),
            r.get("deductions", 0),
            r.get("net", 0),
        ])

    return output.getvalue()

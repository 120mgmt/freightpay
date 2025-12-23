# FreightPay/bookkeeping/export_quickbooks.py

import csv
import io
from typing import List, Dict


def export_quickbooks_csv(ledger: List[Dict]) -> str:
    """
    Exports bookkeeping ledger to a QuickBooks-compatible CSV.
    Import into [QuickBooks](chatgpt://generic-entity?number=0) as a journal/payroll CSV.
    """

    output = io.StringIO()
    writer = csv.writer(output)

# Header row (QB-friendly)
    writer.writerow([
        "Date",
        "Contractor ID",
        "Pay Period",
        "Gross Pay",
        "Reimbursements",
        "Deductions",
        "Net Pay",
        "Memo"
    ])

    for row in ledger:
        writer.writerow([
            row.get("timestamp", "")[:10],
            row.get("contractor_id", ""),
            row.get("pay_period", ""),
            f"{row.get('gross', 0):.2f}",
            f"{row.get('reimbursements', 0):.2f}",
            f"{row.get('deductions', 0):.2f}",
            f"{row.get('net', 0):.2f}",
            "FreightPay Payroll"
        ])

    return output.getvalue()

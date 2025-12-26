# payroll/export_csv.py

import csv
import io
from typing import Dict, Any, List


def settlements_to_csv(payroll_result: Dict[str, Any]) -> str:
    """
    Exports the FULL output of run_payroll() to CSV.

    Expected input shape:
    {
        "results": [
            {
                "contractor_id": ...,
                "base_gross": ...,
                "base_detail": {...},
                "accessorials": {"total": ...},
                "deductions": {"total": ...},
                "gross": ...,
                "net": ...
            }
        ],
        "totals": {...}
    }
    """

    output = io.StringIO()
    writer = csv.writer(output)

    # HEADER (aligned with engine output)
    writer.writerow(
        [
            "contractor_id",
            "pay_type",
            "base_gross",
            "accessorials_total",
            "deductions_total",
            "gross",
            "net",
            "weekly_guarantee",
            "guarantee_topup",
        ]
    )

    rows: List[Dict[str, Any]] = payroll_result.get("results", [])

    for r in rows:
        base_detail = r.get("base_detail") or {}
        accessorials = r.get("accessorials") or {}
        deductions = r.get("deductions") or {}

        writer.writerow(
            [
                r.get(" triggered", r.get("contractor_id", "")),
                base_detail.get("pay_type", ""),
                r.get("base_gross", 0),
                accessorials.get("total", 0),
                deductions.get("total", 0),
                r.get("gross", 0),
                r.get("net", 0),
                base_detail.get("weekly_guarantee", 0),
                base_detail.get("guarantee_topup", 0),
            ]
        )

    # TOTALS ROW
    totals = payroll_result.get("totals") or {}
    writer.writerow([])
    writer.writerow(
        [
            "TOTALS",
            "",
            totals.get("base_gross_total", 0),
            totals.get("accessorials_total", 0),
            totals.get("deductions_total", 0),
            "",
            totals.get("net_total", 0),
            "",
            "",
        ]
    )

    return output.getvalue()

# payroll/engine.py

from typing import Dict, Any, List, Union
from utils.database import get_db_session
from payroll.payroll_run_status import can_edit_payroll_run
from payroll.miles_pay import calculate_miles_pay
from payroll.accessorials import calculate_accessorials
from payroll.deductions import calculate_deductions


def run_payroll(payload: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Dict[str, Any]:
    """
    Accepts either:
        1) {"contractors": [ ... ], "payroll_run_id": "..."} (preferred)
        2) [ ... ] (raw list fallback)

    Returns:
    {
        "results": [...],
        "totals": {
            "base_gross_total": ...,
            "accessorials_total": ...,
            "deductions_total": ...,
            "net_total": ...
        }
    }
    """

    db = get_db_session()

    payroll_run_id = None
    if isinstance(payload, dict):
        payroll_run_id = payload.get("payroll_run_id")

    if payroll_run_id and not can_edit_payroll_run(db, payroll_run_id):
        raise Exception("Payroll run is finalized or locked")

    if isinstance(payload, dict):
        contractors = payload.get("contractors", [])
    else:
        contractors = payload

    results = []
    totals = {
        "base_gross_total": 0,
        "accessorials_total": 0,
        "deductions_total": 0,
        "net_total": 0,
    }

    for contractor in contractors:
        base_gross, base_detail = calculate_miles_pay(contractor)
        access_total, access_detail = calculate_accessorials(contractor)
        deduction_total, deduction_detail = calculate_deductions(contractor)

        net_pay = base_gross + access_total - deduction_total

        results.append(
            {
                "contractor_id": contractor.get("id"),
                "base_gross": base_gross,
                "accessorials": access_total,
                "deductions": deduction_total,
                "net_pay": net_pay,
                "detail": {
                    "base": base_detail,
                    "accessorials": access_detail,
                    "deductions": deduction_detail,
                },
            }
        )

        totals["base_gross_total"] += base_gross
        totals["accessorials_total"] += access_total
        totals["deductions_total"] += deduction_total
        totals["net_total"] += net_pay

    if payroll_run_id:
        db.execute(
            """
            INSERT INTO payroll_runs (
                id,
                base_gross_total,
                accessorials_total,
                deductions_total,
                net_total
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                payroll_run_id,
                totals["base_gross_total"],
                totals["accessorials_total"],
                totals["deductions_total"],
                totals["net_total"],
            ),
        )
        db.commit()

    return {
        "results": results,
        "totals": totals,
    }

# FreightPay/bookkeeping/ledger.py

from datetime import datetime
from typing import List, Dict

LEDGER: List[Dict] = []


def record_payroll_run(
    pay_period: str,
    contractor_id: str,
    gross: float,
    reimbursements: float,
    deductions: float,
    net: float,
):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "pay_period": pay_period,
        "contractor_id": contractor_id,
        "gross": round(gross, 2),
        "reimbursements": round(reimbursements, 2),
        "deductions": round(deductions, 2),
        "net": round(net, 2),
    }
    LEDGER.append(entry)
    return entry


def get_ledger():
    return LEDGER


def clear_ledger():
    LEDGER.clear()

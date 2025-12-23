# FreightPay/bookkeeping/ledger.py

from datetime import datetime
from typing import List, Dict

# In-memory ledger (replace with DB later)
LEDGER: List[Dict] = []


def record_payroll_run(
    pay_period: str,
    contractor_id: str,
    gross: float,
    reimbursements: float,
    deductions: float,
    net: float,
) -> Dict:
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "pay_period": pay_period,
   "contractor_id": contractor_id,
        "gross": round(float(gross), 2),
        "reimbursements": round(float(reimbursements), 2),
        "deductions": round(float(deductions), 2),
        "net": round(float(net), 2),
    }
    LEDGER.append(entry)
    return entry


def get_ledger() -> List[Dict]:
    return LEDGER


def clear_ledger() -> None:
    LEDGER.clear()

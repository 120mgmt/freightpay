# freightpay/bookkeeping/ledger.py

from datetime import datetime
from typing import List, Dict, Any

# NOTE:
# In-memory ledger for MVP.
# Production swap: replace LEDGER with persistent DB table (Postgres).
LEDGER: List[Dict[str, Any]] = []


def record_payroll_run(
    *,
    pay_period: str,
    contractor_id: str,
    gross: float,
    reimbursements: float = 0.0,
    deductions: Dict[str, float],
    taxes: Dict[str, float],
    net: float,
) -> Dict[str, Any]:
    """
    deductions supports:
      - fuel
      - insurance
      - escrow
      - advances
      - maintenance
      - tolls
      - equipment_rental
      - other

    taxes supports:
      - federal
      - state
      - local
      - fica
      - medicare
      - other
    """

    def _round(value: float) -> float:
        return round(float(value or 0.0), 2)

    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "pay_period": pay_period,
        "contractor_id": contractor_id,

        "gross": _round(gross),
        "reimbursements": _round(reimbursements),

        "deductions": {
            "fuel": _round(deductions.get("fuel")),
            "insurance": _round(deductions.get("insurance")),
            "escrow": _round(deductions.get("escrow")),
            "advances": _round(deductions.get("advances")),
            "maintenance": _round(deductions.get("maintenance")),
            "tolls": _round(deductions.get("tolls")),
            "equipment_rental": _round(deductions.get("equipment_rental")),
            "other": _round(deductions.get("other")),
        },

        "taxes": {
            "federal": _round(taxes.get("federal")),
            "state": _round(taxes.get("state")),
            "local": _round(taxes.get("local")),
            "fica": _round(taxes.get("fica")),
            "medicare": _round(taxes.get("medicare")),
            "other": _round(taxes.get("other")),
        },

        "net": _round(net),
    }

    LEDGER.append(entry)
    return entry


def get_ledger() -> List[Dict[str, Any]]:
    return LEDGER

def clear_ledger():
    return True

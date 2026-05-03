from __future__ import annotations

from decimal import Decimal
from typing import Optional, Dict, Any

from services.pricing_cpm_gate import evaluate_offer


class LedgerBlockError(Exception):
    """Raised when CPM gate blocks ledger posting."""
    pass


def guard_ledger_post(
    *,
    company_id: int,
    trip_miles: Decimal,
    offered_rate_total: Optional[Decimal] = None,
    offered_rate_per_mile: Optional[Decimal] = None,
) -> Dict[str, Any]:
    """
    Call this immediately BEFORE creating ledger entries for a load/settlement.

    If CPM decision is 'reject', this raises LedgerBlockError and NOTHING
    should be written to the ledger.
    """
    try:
        result = evaluate_offer(
            company_id=company_id,
            trip_miles=trip_miles,
            offered_rate_total=offered_rate_total,
            offered_rate_per_mile=offered_rate_per_mile,
        )
        return result
    except Exception as e:
        raise LedgerBlockError(str(e)) from e

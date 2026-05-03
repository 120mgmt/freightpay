from __future__ import annotations

from decimal import Decimal
from typing import Optional

from services.pricing_cpm import CPMInputs, compute_cpm
from services.pricing_cpm_store import get_cpm_config


def _d(val) -> Decimal:
    return Decimal(str(val))


def evaluate_offer(
    company_id: int,
    *,
    trip_miles: Decimal,
    offered_rate_total: Optional[Decimal] = None,
    offered_rate_per_mile: Optional[Decimal] = None,
    overrides: Optional[dict] = None,
) -> dict:
    cfg = get_cpm_config(company_id)
    if not cfg:
        raise ValueError("CPM config not set for company")

    o = overrides or {}

    inputs = CPMInputs(
        fixed_monthly_costs=_d(o.get("fixed_monthly_costs", cfg.fixed_monthly_costs)),
        expected_monthly_miles=_d(o.get("expected_monthly_miles", cfg.expected_monthly_miles)),
        maintenance_cpm=_d(o.get("maintenance_cpm", cfg.maintenance_cpm)),
        tolls_cpm=_d(o.get("tolls_cpm", cfg.tolls_cpm)),
        driver_cpm=_d(o.get("driver_cpm", cfg.driver_cpm)),
        other_variable_cpm=_d(o.get("other_variable_cpm", cfg.other_variable_cpm)),
        profit_margin_pct=_d(o.get("profit_margin_pct", cfg.profit_margin_pct)),
        fuel_price_per_gal=_d(o.get("fuel_price_per_gal", cfg.fuel_price_per_gal))
        if o.get("fuel_price_per_gal", cfg.fuel_price_per_gal) is not None
        else None,
        mpg=_d(o.get("mpg", cfg.mpg)) if o.get("mpg", cfg.mpg) is not None else None,
        offered_rate_total=_d(offered_rate_total) if offered_rate_total is not None else None,
        offered_rate_per_mile=_d(offered_rate_per_mile) if offered_rate_per_mile is not None else None,
        trip_miles=_d(trip_miles),
    )

    result = compute_cpm(inputs)

    payload = {
        "company_id": company_id,
        "target_cpm": str(result.target_cpm),
        "offered_cpm": str(result.offered_cpm) if result.offered_cpm is not None else None,
        "decision": result.decision,
        "floor_rate_total": str(result.floor_rate_total) if result.floor_rate_total is not None else None,
    }

    if result.decision == "reject":
        raise ValueError("Offer rejected: below target CPM")

    return payload

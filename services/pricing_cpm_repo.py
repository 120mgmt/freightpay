from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional, Dict

from sqlalchemy import text

from db import db


_CPM_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cpm_config (
  company_id BIGINT PRIMARY KEY,
  fixed_monthly_costs NUMERIC(12,2) NOT NULL,
  expected_monthly_miles NUMERIC(12,2) NOT NULL,
  maintenance_cpm NUMERIC(12,4) NOT NULL DEFAULT 0,
  tolls_cpm NUMERIC(12,4) NOT NULL DEFAULT 0,
  driver_cpm NUMERIC(12,4) NOT NULL DEFAULT 0,
  other_variable_cpm NUMERIC(12,4) NOT NULL DEFAULT 0,
  profit_margin_pct NUMERIC(6,4) NOT NULL DEFAULT 0.2000,
  fuel_price_per_gallon NUMERIC(12,4),
  mpg NUMERIC(12,4),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def ensure_cpm_schema() -> None:
    db.session.execute(text(_CPM_SCHEMA_SQL))
    db.session.commit()


def _d(v: Any) -> Decimal:
    return Decimal(str(v))


def get_cpm_config(company_id: int) -> Optional[Dict[str, Any]]:
    ensure_cpm_schema()
    row = db.session.execute(
        text(
            """
            SELECT
              company_id,
              fixed_monthly_costs,
              expected_monthly_miles,
              maintenance_cpm,
              tolls_cpm,
              driver_cpm,
              other_variable_cpm,
              profit_margin_pct,
              fuel_price_per_gallon,
              mpg
            FROM cpm_config
            WHERE company_id = :company_id
            """
        ),
        {"company_id": int(company_id)},
    ).mappings().first()

    return dict(row) if row else None


def upsert_cpm_config(company_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    ensure_cpm_schema()

    if data.get("fixed_monthly_costs") is None or data.get("expected_monthly_miles") is None:
        raise ValueError("fixed_monthly_costs and expected_monthly_miles are required")

    params = {
        "company_id": int(company_id),
        "fixed_monthly_costs": _d(data["fixed_monthly_costs"]),
        "expected_monthly_miles": _d(data["expected_monthly_miles"]),
        "maintenance_cpm": _d(data.get("maintenance_cpm", 0)),
        "tolls_cpm": _d(data.get("tolls_cpm", 0)),
        "driver_cpm": _d(data.get("driver_cpm", 0)),
        "other_variable_cpm": _d(data.get("other_variable_cpm", 0)),
        "profit_margin_pct": _d(data.get("profit_margin_pct", Decimal("0.20"))),
        "fuel_price_per_gallon": (_d(data["fuel_price_per_gallon"]) if data.get("fuel_price_per_gallon") is not None else None),
        "mpg": (_d(data["mpg"]) if data.get("mpg") is not None else None),
    }

    db.session.execute(
        text(
            """
            INSERT INTO cpm_config (
              company_id,
              fixed_monthly_costs,
              expected_monthly_miles,
              maintenance_cpm,
              tolls_cpm,
              driver_cpm,
              other_variable_cpm,
              profit_margin_pct,
              fuel_price_per_gallon,
              mpg,
              updated_at
            )
            VALUES (
              :company_id,
              :fixed_monthly_costs,
              :expected_monthly_miles,
              :maintenance_cpm,
              :tolls_cpm,
              :driver_cpm,
              :other_variable_cpm,
              :profit_margin_pct,
              :fuel_price_per_gallon,
              :mpg,
              now()
            )
            ON CONFLICT (company_id) DO UPDATE SET
              fixed_monthly_costs = EXCLUDED.fixed_monthly_costs,
              expected_monthly_miles = EXCLUDED.expected_monthly_miles,
              maintenance_cpm = EXCLUDED.maintenance_cpm,
              tolls_cpm = EXCLUDED.tolls_cpm,
              driver_cpm = EXCLUDED.driver_cpm,
              other_variable_cpm = EXCLUDED.other_variable_cpm,
              profit_margin_pct = EXCLUDED.profit_margin_pct,
              fuel_price_per_gallon = EXCLUDED.fuel_price_per_gallon,
              mpg = EXCLUDED.mpg,
              updated_at = now()
            """
        ),
        params,
    )
    db.session.commit()

    cfg = get_cpm_config(company_id)
    if not cfg:
        raise RuntimeError("Failed to save CPM config")

    return cfg

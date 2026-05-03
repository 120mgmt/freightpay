from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

DB_PATH = "./instance/freightpay.sqlite"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_cpm_schema():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cpm_config (
                company_id INTEGER PRIMARY KEY,
                fixed_monthly_costs TEXT NOT NULL,
                expected_monthly_miles TEXT NOT NULL,
                maintenance_cpm TEXT NOT NULL DEFAULT '0',
                tolls_cpm TEXT NOT NULL DEFAULT '0',
                driver_cpm TEXT NOT NULL DEFAULT '0',
                other_variable_cpm TEXT NOT NULL DEFAULT '0',
                profit_margin_pct TEXT NOT NULL DEFAULT '0.20',
                fuel_price_per_gal TEXT,
                mpg TEXT,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        conn.commit()


@dataclass(frozen=True)
class CPMConfig:
    company_id: int
    fixed_monthly_costs: Decimal
    expected_monthly_miles: Decimal
    maintenance_cpm: Decimal
    tolls_cpm: Decimal
    driver_cpm: Decimal
    other_variable_cpm: Decimal
    profit_margin_pct: Decimal
    fuel_price_per_gal: Optional[Decimal]
    mpg: Optional[Decimal]


def _d(val) -> Decimal:
    return Decimal(str(val))


def get_cpm_config(company_id: int) -> Optional[CPMConfig]:
    init_cpm_schema()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM cpm_config WHERE company_id = ?",
            (company_id,),
        ).fetchone()

    if not row:
        return None

    return CPMConfig(
        company_id=company_id,
        fixed_monthly_costs=_d(row["fixed_monthly_costs"]),
        expected_monthly_miles=_d(row["expected_monthly_miles"]),
        maintenance_cpm=_d(row["maintenance_cpm"]),
        tolls_cpm=_d(row["tolls_cpm"]),
        driver_cpm=_d(row["driver_cpm"]),
        other_variable_cpm=_d(row["other_variable_cpm"]),
        profit_margin_pct=_d(row["profit_margin_pct"]),
        fuel_price_per_gal=_d(row["fuel_price_per_gal"]) if row["fuel_price_per_gal"] is not None else None,
        mpg=_d(row["mpg"]) if row["mpg"] is not None else None,
    )


def upsert_cpm_config(company_id: int, data: dict) -> CPMConfig:
    init_cpm_schema()

    with _connect() as conn:
        conn.execute(
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
                fuel_price_per_gal,
                mpg,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(company_id) DO UPDATE SET
                fixed_monthly_costs=excluded.fixed_monthly_costs,
                expected_monthly_miles=excluded.expected_monthly_miles,
                maintenance_cpm=excluded.maintenance_cpm,
                tolls_cpm=excluded.tolls_cpm,
                driver_cpm=excluded.driver_cpm,
                other_variable_cpm=excluded.other_variable_cpm,
                profit_margin_pct=excluded.profit_margin_pct,
                fuel_price_per_gal=excluded.fuel_price_per_gal,
                mpg=excluded.mpg,
                updated_at=datetime('now');
            """,
            (
                company_id,
                str(data["fixed_monthly_costs"]),
                str(data["expected_monthly_miles"]),
                str(data.get("maintenance_cpm", "0")),
                str(data.get("tolls_cpm", "0")),
                str(data.get("driver_cpm", "0")),
                str(data.get("other_variable_cpm", "0")),
                str(data.get("profit_margin_pct", "0.20")),
                str(data.get("fuel_price_per_gal")) if data.get("fuel_price_per_gal") is not None else None,
                str(data.get("mpg")) if data.get("mpg") is not None else None,
            ),
        )
        conn.commit()

    cfg = get_cpm_config(company_id)
    if not cfg:
        raise RuntimeError("Failed to persist CPM config")

    return cfg




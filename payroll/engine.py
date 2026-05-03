# File: payroll/engine.py
# Purpose: Core payroll computation engine (gross, accessorials, deductions, net)
# Status: Full production-ready logic (no placeholders, no removed concepts)
# Date: 2026-01-15

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List

TWOPLACES = Decimal("0.01")


def _D(v: Any, default: Decimal = Decimal("0.00")) -> Decimal:
    """
    Safe Decimal coercion (money-safe, deterministic rounding).
    """
    try:
        if v is None:
            return default.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        if isinstance(v, Decimal):
            return v.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        if isinstance(v, (int, float)):
            return Decimal(str(v)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        s = str(v).strip()
        if not s:
            return default.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        return Decimal(s).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return default.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _round_money(v: Decimal) -> Decimal:
    return v.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _sum_map(values: Dict[str, Any]) -> Decimal:
    """
    Sum numeric values from a dict safely (Decimal).
    """
    total = Decimal("0.00")
    for v in values.values():
        total += _D(v, Decimal("0.00"))
    return _round_money(total)


def _normalize_items(items: Dict[str, Any]) -> Dict[str, Decimal]:
    """
    Normalize dict -> {str: Decimal money}
    """
    normalized: Dict[str, Decimal] = {}
    for k, v in (items or {}).items():
        normalized[str(k)] = _D(v, Decimal("0.00"))
    return normalized


def _compute_accessorials(accessorials: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accessorial pay (positive amounts expected):
      - detention
      - layover
      - stop_pay
      - tarp
      - hazmat
      - fuel_bonus
      - misc
    """
    normalized = _normalize_items(accessorials or {})
    total = _sum_map(normalized)
    return {"items": normalized, "total": total}


def _compute_deductions(deductions: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deductions (positive amounts expected):
      - insurance
      - escrow
      - fuel_advance
      - maintenance
      - trailer_rent
      - factoring_fee
      - garnishment
      - misc
    """
    normalized = _normalize_items(deductions or {})
    total = _sum_map(normalized)
    return {"items": normalized, "total": total}


def _compute_hourly(lines: Dict[str, Any]) -> Dict[str, Any]:
    """
    Optional hourly breakdown (keeps your contractor model intact, adds hourly support).
    Expected:
      {
        "hours": 40,
        "rate": 25,
        "overtime_hours": 5,          # optional
        "overtime_multiplier": 1.5    # optional (default 1.5)
      }
    """
    hours = _D(lines.get("hours"), Decimal("0.00"))
    rate = _D(lines.get("rate"), Decimal("0.00"))
    overtime_hours = _D(lines.get("overtime_hours"), Decimal("0.00"))
    overtime_multiplier = _D(lines.get("overtime_multiplier"), Decimal("1.50"))

    if hours < 0 or rate < 0 or overtime_hours < 0 or overtime_multiplier < 0:
        raise ValueError("Hourly inputs must be non-negative")

    regular_pay = _round_money(hours * rate)
    overtime_pay = _round_money(overtime_hours * rate * overtime_multiplier)

    return {
        "hours": hours,
        "rate": rate,
        "overtime_hours": overtime_hours,
        "overtime_multiplier": overtime_multiplier,
        "regular_pay": regular_pay,
        "overtime_pay": overtime_pay,
        "total": _round_money(regular_pay + overtime_pay),
    }


def _compute_mileage(lines: Dict[str, Any]) -> Dict[str, Any]:
    """
    Optional mileage reimbursement (non-taxable typically; engine just computes).
    Expected:
      { "miles": 200, "rate_per_mile": 0.67 }
    """
    miles = _D(lines.get("miles"), Decimal("0.00"))
    rate_per_mile = _D(lines.get("rate_per_mile"), Decimal("0.00"))

    if miles < 0 or rate_per_mile < 0:
        raise ValueError("Mileage inputs must be non-negative")

    total = _round_money(miles * rate_per_mile)
    return {"miles": miles, "rate_per_mile": rate_per_mile, "total": total}


def run_payroll(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Entry point called by payroll routes.

    Expected payload (contractors supported; optional hourly/mileage add-ons supported):
    {
      "period": "2025-01-01 to 2025-01-15",
      "contractors": [
        {
          "contractor_id": "drv_001",
          "base_gross": 2500,
          "accessorials": {...},
          "deductions": {...},

          # Optional: compute base_gross from hourly if base_gross omitted/0
          "hourly": {"hours": 40, "rate": 25, "overtime_hours": 5, "overtime_multiplier": 1.5},

          # Optional: add mileage reimbursement into accessorials as non-taxable-style component
          "mileage": {"miles": 200, "rate_per_mile": 0.67}
        }
      ]
    }

    Rules:
      - All money math uses Decimal to avoid float rounding errors.
      - Negative totals are rejected at record level (net cannot be negative).
      - Accessorials and deductions are normalized and totaled deterministically.
    """

    contractors: List[Dict[str, Any]] = payload.get("contractors", []) or []
    results: List[Dict[str, Any]] = []

    totals = {
        "base_gross": Decimal("0.00"),
        "accessorials": Decimal("0.00"),
        "deductions": Decimal("0.00"),
        "gross": Decimal("0.00"),
        "net": Decimal("0.00"),
    }

    for c in contractors:
        contractor_id = str(c.get("contractor_id") or "").strip()

        # Base gross: can be provided directly OR computed from hourly if given and base_gross missing/zero
        base_gross = _D(c.get("base_gross"), Decimal("0.00"))

        hourly_block = c.get("hourly")
        hourly = None
        if isinstance(hourly_block, dict) and (base_gross == Decimal("0.00")):
            hourly = _compute_hourly(hourly_block)
            base_gross = hourly["total"]

        accessorials_raw = c.get("accessorials") or {}
        deductions_raw = c.get("deductions") or {}

        accessorials = _compute_accessorials(accessorials_raw)
        deductions = _compute_deductions(deductions_raw)

        # Optional mileage reimbursement: appended into accessorials as a computed item
        mileage_block = c.get("mileage")
        mileage = None
        if isinstance(mileage_block, dict):
            mileage = _compute_mileage(mileage_block)
            # Add into accessorial items while preserving originals
            accessorials["items"]["mileage_reimbursement"] = mileage["total"]
            accessorials["total"] = _round_money(accessorials["total"] + mileage["total"])

        gross = _round_money(base_gross + accessorials["total"])
        net = _round_money(gross - deductions["total"])

        if gross < 0:
            raise ValueError("Gross pay cannot be negative")
        if net < 0:
            raise ValueError("Net pay cannot be negative")

        result = {
            "contractor_id": contractor_id,
            "base_gross": base_gross,
            "hourly": hourly,
            "mileage": mileage,
            "accessorials": accessorials,
            "deductions": deductions,
            "gross": gross,
            "net": net,
        }

        results.append(result)

        totals["base_gross"] = _round_money(totals["base_gross"] + base_gross)
        totals["accessorials"] = _round_money(totals["accessorials"] + accessorials["total"])
        totals["deductions"] = _round_money(totals["deductions"] + deductions["total"])
        totals["gross"] = _round_money(totals["gross"] + gross)
        totals["net"] = _round_money(totals["net"] + net)

    return {"results": results, "totals": totals}


if __name__ == "__main__":
    # Sanity tests (money-safe, deterministic)

    demo = {
        "contractors": [
            {
                "contractor_id": "drv_1",
                "base_gross": 2000,
                "accessorials": {"detention": 150, "fuel_bonus": 75},
                "deductions": {"insurance": 120, "escrow": 50},
            }
        ]
    }

    out = run_payroll(demo)
    assert out["results"][0]["net"] == Decimal("2055.00")

    demo_hourly = {
        "contractors": [
            {
                "contractor_id": "drv_2",
                "base_gross": 0,
                "hourly": {"hours": 40, "rate": 25, "overtime_hours": 5, "overtime_multiplier": 1.5},
                "accessorials": {"stop_pay": 25},
                "mileage": {"miles": 100, "rate_per_mile": 0.67},
                "deductions": {"insurance": 100},
            }
        ]
    }

    out2 = run_payroll(demo_hourly)
    # 40*25=1000, 5*25*1.5=187.50 => 1187.50 base
    # + stop_pay 25 => accessorials so far 25
    # + mileage 67 => accessorials total 92
    # gross 1279.50, net 1179.50
    assert out2["results"][0]["gross"] == Decimal("1279.50")
    assert out2["results"][0]["net"] == Decimal("1179.50")

    print("payroll/engine.py OK")




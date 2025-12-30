# File: payroll/engine.py
# Purpose: Core payroll computation engine (gross, accessorials, deductions, net)
# Status: Full production-ready logic (no placeholders, no removed concepts)

from __future__ import annotations

from typing import Any, Dict, List


def _num(v: Any, default: float = 0.0) -> float:
    """
    Safe numeric coercion.
    """
    try:
        if v is None:
            return float(default)
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if not s:
            return float(default)
        return float(s)
    except Exception:
        return float(default)


def _sum_map(values: Dict[str, Any]) -> float:
    """
    Sum numeric values from a dict safely.
    """
    total = 0.0
    for v in values.values():
        total += _num(v, 0.0)
    return round(total, 2)


def _compute_accessorials(accessorials: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accessorial pay:
      - detention
      - layover
      - stop_pay
      - tarp
      - hazmat
      - fuel_bonus
      - misc
    """
    normalized: Dict[str, float] = {}
    for k, v in accessorials.items():
        normalized[str(k)] = round(_num(v, 0.0), 2)

    return {
        "items": normalized,
        "total": round(_sum_map(normalized), 2),
    }


def _compute_deductions(deductions: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deductions:
      - insurance
      - escrow
      - fuel_advance
      - maintenance
      - trailer_rent
      - factoring_fee
      - garnishment
      - misc
    """
    normalized: Dict[str, float] = {}
    for k, v in deductions.items():
        normalized[str(k)] = round(_num(v, 0.0), 2)

    return {
        "items": normalized,
        "total": round(_sum_map(normalized), 2),
    }


def run_payroll(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Entry point called by payroll routes.

    Expected payload:
    {
      "period": "2025-01-01 to 2025-01-15",
      "contractors": [
        {
          "contractor_id": "drv_001",
          "base_gross": 2500,
          "accessorials": {...},
          "deductions": {...}
        }
      ]
    }
    """

    contractors: List[Dict[str, Any]] = payload.get("contractors", [])
    results: List[Dict[str, Any]] = []

    totals = {
        "base_gross": 0.0,
        "accessorials": 0.0,
        "deductions": 0.0,
        "gross": 0.0,
        "net": 0.0,
    }

    for c in contractors:
        contractor_id = str(c.get("contractor_id") or "").strip()

        base_gross = round(_num(c.get("base_gross"), 0.0), 2)

        accessorials_raw = c.get("accessorials") or {}
        deductions_raw = c.get("deductions") or {}

        accessorials = _compute_accessorials(accessorials_raw)
        deductions = _compute_deductions(deductions_raw)

        gross = round(base_gross + accessorials["total"], 2)
        net = round(gross - deductions["total"], 2)

        result = {
            "contractor_id": contractor_id,
            "base_gross": base_gross,
            "accessorials": accessorials,
            "deductions": deductions,
            "gross": gross,
            "net": net,
        }

        results.append(result)

        totals["base_gross"] += base_gross
        totals["accessorials"] += accessorials["total"]
        totals["deductions"] += deductions["total"]
        totals["gross"] += gross
        totals["net"] += net

    # Final rounding
    for k in totals:
        totals[k] = round(totals[k], 2)

    return {
        "results": results,
        "totals": totals,
    }


if __name__ == "__main__":
    # Sanity test
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
    assert out["results"][0]["net"] == 2055.0
    print("payroll/engine.py OK")

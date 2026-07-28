"""Mileage arithmetic in the payroll engine.

Regression cover for the rate-truncation bug: rate_per_mile used to be coerced
through the money helper (_D), which quantized it to 2 decimals BEFORE the
multiply. A $0.655/mi rate became $0.66, so 2,500 miles billed $1,650.00
instead of $1,637.50 — and the figure changed between the on-screen preview
and the saved run.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)


def test_three_decimal_rate_is_not_rounded_before_multiply():
    from decimal import Decimal

    from payroll.engine import _compute_mileage

    out = _compute_mileage({"miles": 2500, "rate_per_mile": 0.655})
    assert out["total"] == Decimal("1637.50")
    assert out["rate_per_mile"] == Decimal("0.655")


def test_another_three_decimal_rate():
    from decimal import Decimal

    from payroll.engine import _compute_mileage

    out = _compute_mileage({"miles": 1000, "rate_per_mile": 0.575})
    assert out["total"] == Decimal("575.00")


def test_two_decimal_rate_still_exact():
    from decimal import Decimal

    from payroll.engine import _compute_mileage

    out = _compute_mileage({"miles": 1200, "rate_per_mile": 0.60})
    assert out["total"] == Decimal("720.00")


def test_product_is_rounded_to_cents():
    from decimal import Decimal

    from payroll.engine import _compute_mileage

    # 333 * 0.4444 = 147.9852 -> 147.99 (only the money is rounded, and the
    # full-precision rate is what makes the cent land correctly)
    out = _compute_mileage({"miles": 333, "rate_per_mile": 0.4444})
    assert out["total"] == Decimal("147.99")


def test_string_inputs_are_accepted():
    from decimal import Decimal

    from payroll.engine import _compute_mileage

    out = _compute_mileage({"miles": "2500", "rate_per_mile": "0.655"})
    assert out["total"] == Decimal("1637.50")


def test_negative_mileage_rejected():
    import pytest

    from payroll.engine import _compute_mileage

    with pytest.raises(ValueError):
        _compute_mileage({"miles": -1, "rate_per_mile": 0.50})
    with pytest.raises(ValueError):
        _compute_mileage({"miles": 100, "rate_per_mile": -0.50})


def test_totals_aggregate_mileage_and_miles():
    from decimal import Decimal

    from payroll.engine import run_payroll

    out = run_payroll(
        {
            "contractors": [
                {
                    "contractor_id": "d1",
                    "base_gross": 500,
                    "mileage": {"miles": 2500, "rate_per_mile": 0.655},
                    "accessorials": {"tonu": 150},
                    "deductions": {"fuel_advance": 200},
                },
                {
                    "contractor_id": "d2",
                    "base_gross": 0,
                    "mileage": {"miles": 1000, "rate_per_mile": 0.575},
                },
            ]
        }
    )

    totals = out["totals"]
    assert totals["mileage"] == Decimal("2212.50")  # 1637.50 + 575.00
    assert totals["miles"] == Decimal("3500")
    # d1: 500 + 1637.50 + 150 = 2287.50 gross, less 200 = 2087.50 net
    assert out["results"][0]["gross"] == Decimal("2287.50")
    assert out["results"][0]["net"] == Decimal("2087.50")


def test_mileage_counted_once_in_gross():
    from decimal import Decimal

    from payroll.engine import run_payroll

    out = run_payroll(
        {
            "contractors": [
                {
                    "contractor_id": "d1",
                    "base_gross": 0,
                    "mileage": {"miles": 100, "rate_per_mile": 1},
                }
            ]
        }
    )
    line = out["results"][0]
    # Mileage lands in accessorials exactly once and flows to gross once.
    assert line["accessorials"]["items"]["mileage_reimbursement"] == Decimal("100.00")
    assert line["accessorials"]["total"] == Decimal("100.00")
    assert line["gross"] == Decimal("100.00")


def test_run_without_mileage_is_unchanged():
    from decimal import Decimal

    from payroll.engine import run_payroll

    out = run_payroll(
        {
            "contractors": [
                {
                    "contractor_id": "x",
                    "base_gross": 2000,
                    "accessorials": {"detention": 150, "fuel_bonus": 75},
                    "deductions": {"insurance": 120, "escrow": 50},
                }
            ]
        }
    )
    assert out["results"][0]["net"] == Decimal("2055.00")
    assert out["results"][0]["mileage"] is None
    assert out["totals"]["mileage"] == Decimal("0.00")
    assert out["totals"]["miles"] == Decimal("0")

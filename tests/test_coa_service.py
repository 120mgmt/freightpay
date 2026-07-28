# tests/test_coa_service.py
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)


def test_to_int_company_id_valid():
    from services.coa import _to_int_company_id
    assert _to_int_company_id("1") == 1
    assert _to_int_company_id(5) == 5


def test_to_int_company_id_invalid():
    from services.coa import _to_int_company_id
    try:
        _to_int_company_id("")
        assert False
    except ValueError:
        assert True


def test_code_str():
    from services.coa import _code_str
    assert _code_str("1000") == "1000"


def test_validate_code_range_valid():
    from services.coa import _validate_code_range
    _validate_code_range("1000")
    _validate_code_range("5999")


def test_validate_code_range_invalid():
    from services.coa import _validate_code_range
    try:
        _validate_code_range("999")
        assert False
    except ValueError:
        assert True


def test_bool_helper_true():
    from services.coa import _to_bool
    assert _to_bool("true", False) is True
    assert _to_bool("1", False) is True
    assert _to_bool("yes", False) is True


def test_bool_helper_false():
    from services.coa import _to_bool
    assert _to_bool("false", True) is False
    assert _to_bool("0", True) is False
    assert _to_bool("no", True) is False


def test_bool_helper_default():
    from services.coa import _to_bool
    assert _to_bool(None, True) is True
    assert _to_bool("unknown", False) is False


def test_every_default_code_passes_the_seed_validator():
    """Guards the whole seed: one out-of-range code 500s /coa/seed for every company."""
    from models.chart_of_accounts import default_coa_rows
    from services.coa import _validate_code_range

    for row in default_coa_rows():
        _validate_code_range(row["account_code"])


def test_default_account_codes_are_unique():
    from models.chart_of_accounts import default_coa_rows

    codes = [r["account_code"] for r in default_coa_rows()]
    assert len(codes) == len(set(codes))


def test_trucking_expense_categories_are_seeded():
    from models.chart_of_accounts import default_coa_rows

    by_code = {r["account_code"]: r for r in default_coa_rows()}
    expected = {
        "5300": "Fuel",
        "5310": "Maintenance & Repairs",
        "5320": "Insurance",
        "5330": "Tolls",
        "5340": "Driver Pay",
        "5350": "Office & Admin",
        "5360": "Software & Subscriptions",
        "5370": "Load Expenses",
        "5380": "Permits & Licenses",
        "5390": "Miscellaneous",
    }
    for code, name in expected.items():
        assert code in by_code, f"missing expense category {code} {name}"
        assert by_code[code]["name"] == name
        assert by_code[code]["account_type"] == "expense"
        assert by_code[code]["normal_balance"] == "debit"


def test_trucking_categories_are_user_manageable():
    """They are everyday categories, not locked system accounts."""
    from models.chart_of_accounts import trucking_expense_rows

    assert all(r["is_system"] is False for r in trucking_expense_rows())


def test_trucking_expense_rows_returns_fresh_dicts():
    from models.chart_of_accounts import trucking_expense_rows

    first = trucking_expense_rows()
    first[0]["name"] = "mutated"
    assert trucking_expense_rows()[0]["name"] == "Fuel"

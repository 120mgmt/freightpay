# tests/test_ci_smoke.py
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

def test_default_coa_rows_present():
    from models.chart_of_accounts import default_coa_rows
    rows = default_coa_rows()
    assert isinstance(rows, list)
    assert len(rows) > 0
    assert isinstance(rows[0], dict)
    assert rows[0]["account_code"]

def test_company_id_parser():
    from services.coa import _to_int_company_id
    assert _to_int_company_id("1") == 1
    assert _to_int_company_id(2) == 2

def test_code_helpers():
    from services.coa import _code_str, _validate_code_range
    assert _code_str("1000") == "1000"
    _validate_code_range("1000")

def test_bool_helper():
    from services.coa import _to_bool
    assert _to_bool("true", False) is True
    assert _to_bool("false", True) is False

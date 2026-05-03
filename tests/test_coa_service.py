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

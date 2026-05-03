# File: integrations/provider/validation.py
# Purpose: Enterprise Provider Payload Validation Layer (Strict, Deterministic, Financial-Safe)
# Status: Enterprise Hardened
# Date: 2026-02-26
#
# Guarantees:
# - No silent coercion
# - Strict type validation
# - Decimal-safe monetary validation
# - Deterministic normalization
# - Explicit error reporting

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Iterable


# ============================================================
# VALIDATION EXCEPTION
# ============================================================

class ProviderValidationError(Exception):
    pass


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _require_dict(obj: Any, name: str) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        raise ProviderValidationError(f"{name} must be object")
    return obj


def _require_list(obj: Any, name: str) -> List[Any]:
    if not isinstance(obj, list):
        raise ProviderValidationError(f"{name} must be array")
    return obj


def _require_non_empty_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProviderValidationError(f"{name} must be non-empty string")
    return value.strip()


def _require_int(value: Any, name: str) -> int:
    if not isinstance(value, int):
        raise ProviderValidationError(f"{name} must be integer")
    return value


def _require_decimal(value: Any, name: str) -> Decimal:
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ProviderValidationError(f"{name} must be numeric")
    return dec


# ============================================================
# BASE PAYLOAD VALIDATION
# ============================================================

def validate_base_payload(payload: Dict[str, Any]) -> None:
    payload = _require_dict(payload, "payload")

    required = ["company_id", "payroll_run_uuid"]

    for field in required:
        if field not in payload:
            raise ProviderValidationError(f"missing required field: {field}")

    _require_int(payload["company_id"], "company_id")
    _require_non_empty_str(str(payload["payroll_run_uuid"]), "payroll_run_uuid")


# ============================================================
# EARNINGS VALIDATION
# ============================================================

def validate_earnings(earnings: Iterable[Dict[str, Any]]) -> None:
    earnings = _require_list(earnings, "earnings")

    for idx, item in enumerate(earnings):
        item = _require_dict(item, f"earnings[{idx}]")

        _require_non_empty_str(item.get("worker_uuid"), f"earnings[{idx}].worker_uuid")
        _require_decimal(item.get("amount"), f"earnings[{idx}].amount")

        if "type" in item:
            _require_non_empty_str(item.get("type"), f"earnings[{idx}].type")


# ============================================================
# DEDUCTIONS VALIDATION
# ============================================================

def validate_deductions(deductions: Iterable[Dict[str, Any]]) -> None:
    deductions = _require_list(deductions, "deductions")

    for idx, item in enumerate(deductions):
        item = _require_dict(item, f"deductions[{idx}]")

        _require_non_empty_str(item.get("worker_uuid"), f"deductions[{idx}].worker_uuid")
        _require_decimal(item.get("amount"), f"deductions[{idx}].amount")

        if "type" in item:
            _require_non_empty_str(item.get("type"), f"deductions[{idx}].type")


# ============================================================
# TAX VALIDATION + NORMALIZATION
# ============================================================

def normalize_tax_objects(taxes: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    taxes = _require_list(taxes, "taxes")

    normalized: List[Dict[str, Any]] = []

    for idx, tax in enumerate(taxes):
        tax = _require_dict(tax, f"taxes[{idx}]")

        tax_type = _require_non_empty_str(tax.get("type"), f"taxes[{idx}].type")
        amount = _require_decimal(tax.get("amount"), f"taxes[{idx}].amount")

        normalized.append(
            {
                "type": tax_type.lower(),
                "amount": str(amount),  # preserve precision
            }
        )

    return normalized


# ============================================================
# MASTER VALIDATION ENTRY POINT
# ============================================================

def validate_full_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    validate_base_payload(payload)

    if "earnings" in payload:
        validate_earnings(payload["earnings"])

    if "deductions" in payload:
        validate_deductions(payload["deductions"])

    if "taxes" in payload:
        payload["taxes"] = normalize_tax_objects(payload["taxes"])

    return payload

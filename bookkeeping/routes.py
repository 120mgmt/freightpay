# File: bookkeeping/routes.py
# Purpose: Enterprise-grade bookkeeping API routes for ledger retrieval,
#          payroll posting, and destructive-operation protection.

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from bookkeeping.ledger import get_ledger, clear_ledger, record_payroll_run
from models.contractor import Contractor

bookkeeping_bp = Blueprint("bookkeeping", __name__, url_prefix="/api/bookkeeping")


TWOPLACES = Decimal("0.01")


def _json_error(message: str, status: int = 400, code: str = "BAD_REQUEST"):
    return jsonify({"error": code, "message": message}), status


def _require_auth():
    verify_jwt_in_request()
    identity = get_jwt_identity()

    if not identity:
        return None, _json_error("Authentication required", 401, "UNAUTHORIZED")

    if isinstance(identity, dict):
        company_id = identity.get("company_id")
        user_id = identity.get("user_id") or identity.get("id")
        role = identity.get("role")
    else:
        company_id = None
        user_id = None
        role = None

    if not company_id:
        return None, _json_error("Company context is required", 403, "FORBIDDEN")

    return {
        "company_id": int(company_id),
        "user_id": user_id,
        "role": role,
    }, None


def _to_decimal(value: Any, field_name: str) -> Decimal:
    try:
        dec = Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid numeric value for {field_name}")
    return dec


def _require_payload(required_fields: list[str], payload: dict[str, Any]):
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(f"Missing fields: {missing}")


def _validated_payload(payload: dict[str, Any]) -> dict[str, Any]:
    _require_payload(
        [
            "pay_period",
            "contractor_id",
            "gross",
            "reimbursements",
            "deductions",
            "net",
        ],
        payload,
    )

    pay_period = str(payload["pay_period"]).strip()
    if not pay_period:
        raise ValueError("pay_period is required")

    contractor_id = payload["contractor_id"]
    try:
        contractor_id = int(contractor_id)
    except (TypeError, ValueError):
        raise ValueError("contractor_id must be an integer")

    gross = _to_decimal(payload["gross"], "gross")
    reimbursements = _to_decimal(payload["reimbursements"], "reimbursements")
    deductions = _to_decimal(payload["deductions"], "deductions")
    net = _to_decimal(payload["net"], "net")

    if gross < 0:
        raise ValueError("gross cannot be negative")
    if reimbursements < 0:
        raise ValueError("reimbursements cannot be negative")
    if deductions < 0:
        raise ValueError("deductions cannot be negative")
    if net < 0:
        raise ValueError("net cannot be negative")

    expected_net = (gross + reimbursements - deductions).quantize(
        TWOPLACES, rounding=ROUND_HALF_UP
    )
    if expected_net != net:
        raise ValueError("net does not reconcile with gross + reimbursements - deductions")

    return {
        "pay_period": pay_period,
        "contractor_id": contractor_id,
        "gross": gross,
        "reimbursements": reimbursements,
        "deductions": deductions,
        "net": net,
    }


def _get_company_contractor(company_id: int, contractor_id: int):
    contractor = Contractor.query.filter_by(
        id=contractor_id,
        company_id=company_id,
        is_active=True,
    ).first()

    if not contractor:
        raise LookupError("Contractor not found for this company")

    return contractor


def _filter_ledger_for_company(ledger: list[dict[str, Any]], company_id: int):
    filtered = []
    for entry in ledger:
        if not isinstance(entry, dict):
            continue

        entry_company_id = entry.get("company_id")
        if entry_company_id is None:
            # Preserve backward compatibility for legacy ledger entries that were
            # recorded before company scoping existed. Do not expose them.
            continue

        try:
            entry_company_id = int(entry_company_id)
        except (TypeError, ValueError):
            continue

        if entry_company_id == company_id:
            filtered.append(entry)

    return filtered


@bookkeeping_bp.get("/ledger")
def api_get_ledger():
    auth, auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        ledger = get_ledger()
        scoped_ledger = _filter_ledger_for_company(ledger, auth["company_id"])
        return jsonify({"ledger": scoped_ledger}), 200
    except Exception as exc:
        current_app.logger.exception("Failed to fetch ledger")
        return jsonify(
            {
                "error": "LEDGER_FETCH_FAILED",
                "message": "Failed to fetch ledger",
                "detail": str(exc),
            }
        ), 500


@bookkeeping_bp.post("/ledger/record")
def api_record_payroll():
    auth, auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        payload = request.get_json(force=True) or {}
        values = _validated_payload(payload)

        contractor = _get_company_contractor(
            auth["company_id"],
            values["contractor_id"],
        )

        entry = record_payroll_run(
            pay_period=values["pay_period"],
            contractor_id=values["contractor_id"],
            gross=float(values["gross"]),
            reimbursements=float(values["reimbursements"]),
            deductions=float(values["deductions"]),
            net=float(values["net"]),
        )

        if isinstance(entry, dict):
            entry.setdefault("company_id", auth["company_id"])
            entry.setdefault("contractor_name", contractor.effective_name)
            entry.setdefault("recorded_by_user_id", auth["user_id"])

        return jsonify({"entry": entry}), 201

    except ValueError as exc:
        return jsonify(
            {
                "error": "VALIDATION_ERROR",
                "message": str(exc),
            }
        ), 400

    except LookupError as exc:
        return jsonify(
            {
                "error": "NOT_FOUND",
                "message": str(exc),
            }
        ), 404

    except Exception as exc:
        current_app.logger.exception("Failed to record payroll ledger entry")
        return jsonify(
            {
                "error": "LEDGER_RECORD_FAILED",
                "message": "Failed to record payroll entry",
                "detail": str(exc),
            }
        ), 500


@bookkeeping_bp.post("/ledger/clear")
def api_clear_ledger():
    auth, auth_error = _require_auth()
    if auth_error:
        return auth_error

    if auth.get("role") not in {"admin", "owner", "super_admin"}:
        return _json_error("Admin access required", 403, "FORBIDDEN")

    if current_app.config.get("ENV") == "production" or (
        current_app.config.get("DEBUG") is False
        and current_app.config.get("TESTING") is not True
        and current_app.config.get("PROPAGATE_EXCEPTIONS") is not True
    ):
        return _json_error(
            "Ledger clear is disabled outside local development",
            403,
            "OPERATION_NOT_ALLOWED",
        )

    try:
        payload = request.get_json(force=True) or {}
        if payload.get("confirm") is not True:
            return _json_error(
                'Set {"confirm": true} in request body to clear ledger',
                400,
                "CONFIRMATION_REQUIRED",
            )

        clear_ledger()

        return jsonify({"status": "cleared"}), 200

    except Exception as exc:
        current_app.logger.exception("Failed to clear ledger")
        return jsonify(
            {
                "error": "LEDGER_CLEAR_FAILED",
                "message": "Failed to clear ledger",
                "detail": str(exc),
            }
        ), 500

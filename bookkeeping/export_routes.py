# File: bookkeeping/export_routes.py
# Purpose: Enterprise-grade bookkeeping export routes for ledger CSV / JSON export
#          with tenant isolation, auth enforcement, and spreadsheet-safe output.

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from bookkeeping.ledger import get_ledger

bookkeeping_export_bp = Blueprint(
    "bookkeeping_export_bp",
    __name__,
    url_prefix="/api/bookkeeping/export",
)


TWOPLACES = Decimal("0.01")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_error(message: str, status: int = 400, code: str = "BAD_REQUEST"):
    return jsonify({"error": code, "message": message}), status


def _require_auth():
    verify_jwt_in_request()
    identity = get_jwt_identity()

    if not identity:
        return None, _json_error("Authentication required", 401, "UNAUTHORIZED")

    company_id = None
    user_id = None
    role = None

    if isinstance(identity, dict):
        company_id = identity.get("company_id")
        user_id = identity.get("user_id") or identity.get("id")
        role = identity.get("role")

    header_company_id = request.headers.get("X-Company-Id")
    if header_company_id:
        try:
            header_company_id = int(str(header_company_id).strip())
        except (TypeError, ValueError):
            return None, _json_error(
                "Invalid X-Company-Id header",
                400,
                "INVALID_COMPANY_ID",
            )

        if company_id is not None and int(company_id) != header_company_id:
            return None, _json_error("Company scope mismatch", 403, "FORBIDDEN")

        company_id = header_company_id

    try:
        company_id = int(company_id)
    except (TypeError, ValueError):
        return None, _json_error("Company context is required", 403, "FORBIDDEN")

    return {
        "company_id": company_id,
        "user_id": user_id,
        "role": role,
    }, None


def _safe_decimal(value: Any) -> str:
    try:
        return str(
            Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        )
    except (InvalidOperation, TypeError, ValueError):
        return "0.00"


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    text_value = str(value)
    if text_value[:1] in ("=", "+", "-", "@"):
        return "'" + text_value
    return text_value


def _normalize_jsonish(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (dict, list)):
        return value

    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="ignore")

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return value

    return value


def _extract_company_id(entry: dict[str, Any]) -> int | None:
    for key in ("company_id", "tenant_id"):
        if key in entry and entry.get(key) is not None:
            try:
                return int(entry.get(key))
            except (TypeError, ValueError):
                return None
    return None


def _normalize_ledger_entry(entry: dict[str, Any], company_id: int) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None

    entry_company_id = _extract_company_id(entry)
    if entry_company_id is None or entry_company_id != company_id:
        return None

    metadata = _normalize_jsonish(entry.get("metadata"))
    source_payload = _normalize_jsonish(entry.get("source_payload"))
    source_run_ids = _normalize_jsonish(entry.get("source_run_ids"))

    if not isinstance(metadata, dict):
        metadata = {}

    if not isinstance(source_payload, (dict, list)):
        source_payload = {}

    if not isinstance(source_run_ids, list):
        source_run_ids = []

    normalized = {
        "entry_id": entry.get("entry_id") or entry.get("id"),
        "company_id": entry_company_id,
        "entry_type": entry.get("entry_type") or entry.get("type") or "ledger",
        "entry_date": entry.get("entry_date")
        or entry.get("date")
        or entry.get("created_at")
        or entry.get("timestamp"),
        "pay_period": entry.get("pay_period"),
        "contractor_id": entry.get("contractor_id"),
        "contractor_name": entry.get("contractor_name"),
        "gross": _safe_decimal(entry.get("gross")),
        "reimbursements": _safe_decimal(entry.get("reimbursements")),
        "deductions": _safe_decimal(entry.get("deductions")),
        "net": _safe_decimal(entry.get("net")),
        "debit_account_code": entry.get("debit_account_code"),
        "credit_account_code": entry.get("credit_account_code"),
        "currency": entry.get("currency") or "USD",
        "memo": entry.get("memo") or entry.get("description"),
        "recorded_by_user_id": entry.get("recorded_by_user_id"),
        "source_run_ids": source_run_ids,
        "metadata": metadata,
        "source_payload": source_payload,
        "created_at": entry.get("created_at"),
        "updated_at": entry.get("updated_at"),
    }

    return normalized


def _get_company_ledger(company_id: int) -> list[dict[str, Any]]:
    raw_ledger = get_ledger()
    if not isinstance(raw_ledger, list):
        raise ValueError("Ledger backend returned invalid data")

    results: list[dict[str, Any]] = []
    for item in raw_ledger:
        normalized = _normalize_ledger_entry(item, company_id)
        if normalized is not None:
            results.append(normalized)

    results.sort(
        key=lambda x: (
            _safe_text(x.get("entry_date")),
            _safe_text(x.get("created_at")),
            _safe_text(x.get("entry_id")),
        ),
        reverse=True,
    )
    return results


def _build_csv(ledger_rows: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(
        [
            "entry_id",
            "company_id",
            "entry_type",
            "entry_date",
            "pay_period",
            "contractor_id",
            "contractor_name",
            "gross",
            "reimbursements",
            "deductions",
            "net",
            "debit_account_code",
            "credit_account_code",
            "currency",
            "memo",
            "recorded_by_user_id",
            "source_run_ids",
            "metadata",
            "created_at",
            "updated_at",
        ]
    )

    for row in ledger_rows:
        writer.writerow(
            [
                _safe_text(row.get("entry_id")),
                _safe_text(row.get("company_id")),
                _safe_text(row.get("entry_type")),
                _safe_text(row.get("entry_date")),
                _safe_text(row.get("pay_period")),
                _safe_text(row.get("contractor_id")),
                _safe_text(row.get("contractor_name")),
                _safe_text(row.get("gross")),
                _safe_text(row.get("reimbursements")),
                _safe_text(row.get("deductions")),
                _safe_text(row.get("net")),
                _safe_text(row.get("debit_account_code")),
                _safe_text(row.get("credit_account_code")),
                _safe_text(row.get("currency")),
                _safe_text(row.get("memo")),
                _safe_text(row.get("recorded_by_user_id")),
                _safe_text(",".join(str(x) for x in row.get("source_run_ids", []))),
                _safe_text(json.dumps(row.get("metadata", {}), sort_keys=True)),
                _safe_text(row.get("created_at")),
                _safe_text(row.get("updated_at")),
            ]
        )

    csv_data = buffer.getvalue()
    buffer.close()
    return csv_data


@bookkeeping_export_bp.get("/ledger.json")
def export_ledger_json():
    auth, auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        ledger_rows = _get_company_ledger(auth["company_id"])
        return jsonify(
            {
                "generated_at": _utc_now_iso(),
                "company_id": auth["company_id"],
                "entry_count": len(ledger_rows),
                "ledger": ledger_rows,
            }
        ), 200
    except ValueError as exc:
        return _json_error(str(exc), 500, "LEDGER_BACKEND_ERROR")
    except Exception as exc:
        return jsonify(
            {
                "error": "LEDGER_EXPORT_FAILED",
                "message": "Failed to export ledger JSON",
                "detail": str(exc),
            }
        ), 500


@bookkeeping_export_bp.get("/ledger.csv")
def export_ledger_csv():
    auth, auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        ledger_rows = _get_company_ledger(auth["company_id"])
        csv_data = _build_csv(ledger_rows)
        filename = (
            f"bookkeeping_ledger_{auth['company_id']}_"
            f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.csv"
        )

        return Response(
            csv_data,
            mimetype="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )
    except ValueError as exc:
        return _json_error(str(exc), 500, "LEDGER_BACKEND_ERROR")
    except Exception as exc:
        return jsonify(
            {
                "error": "LEDGER_EXPORT_FAILED",
                "message": "Failed to export ledger CSV",
                "detail": str(exc),
            }
        ), 500

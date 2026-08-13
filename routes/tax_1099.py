from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from sqlalchemy import text

from db import db
from models.contractor import Contractor


tax_1099_bp = Blueprint("tax_1099_bp", __name__, url_prefix="/tax/1099")


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
            return None, _json_error("Invalid X-Company-Id header", 400, "INVALID_COMPANY_ID")

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


def _parse_year(raw: Any) -> int:
    if raw is None:
        return datetime.now(timezone.utc).year
    try:
        year = int(str(raw).strip())
    except (TypeError, ValueError):
        raise ValueError("year must be a valid integer")

    current_year = datetime.now(timezone.utc).year
    if year < 2000 or year > current_year + 1:
        raise ValueError("year is out of allowed range")
    return year


def _safe_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value)).quantize(TWOPLACES)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def _safe_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return None


def _normalize_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="ignore")
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def _coalesce_dict(*candidates: Any) -> dict[str, Any]:
    for candidate in candidates:
        parsed = _normalize_json(candidate)
        if isinstance(parsed, dict):
            return parsed
    return {}


def _coalesce_list(*candidates: Any) -> list[Any]:
    for candidate in candidates:
        parsed = _normalize_json(candidate)
        if isinstance(parsed, list):
            return parsed
    return []


def _parse_date_like(value: Any) -> datetime | None:
    """A plain date/datetime string, OR a "<start> to <end>" period range
    (the shape the live frontend sends) — returns the end of the range."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text_value = str(value).strip()
    if not text_value:
        return None
    if " to " in text_value:
        text_value = text_value.split(" to ")[-1].strip()
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ):
        try:
            return datetime.strptime(text_value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text_value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_run_date(row: dict[str, Any]) -> datetime | None:
    # payload_json is where the real request body lives — the live
    # payroll_runs schema (migrations/versions/20260401_payroll_runs.py) has
    # no "period", "pay_date" or "period_end" columns at all, only
    # run_id/company_id/created_at/status/payload_json/results_json/
    # finalized/finalized_at. The frontend payload only ever carries a single
    # "period" string shaped "<start> to <end>".
    payload = _coalesce_dict(row.get("payload_json"), row.get("payload"))

    # Priority 1: an explicit date the run actually declares — this is what
    # tax-year classification must key off, including for a settlement
    # entered after the fact for an earlier period.
    for candidate in (
        row.get("pay_date"),
        row.get("period_end"),
        row.get("check_date"),
        payload.get("pay_date"),
        payload.get("period_end"),
        payload.get("period_start"),
        row.get("period"),
        payload.get("period"),
    ):
        parsed = _parse_date_like(candidate)
        if parsed is not None:
            return parsed

    # Priority 2 (last resort): when a run declares no period at all, fall
    # back to when the record itself was touched. created_at/finalized_at
    # are epoch-seconds BigInteger, not text.
    for candidate in (row.get("created_at"), row.get("executed_at"), row.get("updated_at")):
        if candidate is None:
            continue
        if isinstance(candidate, datetime):
            return candidate
        if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
            try:
                return datetime.fromtimestamp(candidate, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                continue
        parsed = _parse_date_like(candidate)
        if parsed is not None:
            return parsed

    return None


def _sum_nested_amounts(container: Any) -> Decimal:
    total = Decimal("0.00")
    if isinstance(container, dict):
        for value in container.values():
            total += _safe_decimal(value)
    elif isinstance(container, list):
        for item in container:
            if isinstance(item, dict):
                if "amount" in item:
                    total += _safe_decimal(item.get("amount"))
                else:
                    for value in item.values():
                        total += _safe_decimal(value)
            else:
                total += _safe_decimal(item)
    else:
        total += _safe_decimal(container)
    return total.quantize(TWOPLACES)


def _extract_candidate_lists(row: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _coalesce_dict(
        row.get("payload_json"),
        row.get("payload"),
        row.get("request_payload"),
        row.get("input_payload"),
    )
    results = _coalesce_dict(
        row.get("results_json"),
        row.get("results"),
        row.get("execution_results"),
        row.get("output_json"),
    )

    def _pull(source: dict[str, Any]) -> list[Any]:
        found: list[Any] = []
        for key in (
            "contractors",
            "results",
            "settlements",
            "payments",
            "worker_results",
            "contractor_results",
            "items",
            "entries",
        ):
            value = source.get(key)
            if isinstance(value, list):
                found.extend(value)
        return found

    # results_json (the computed settlement — gross/net/accessorials/
    # deductions after run_payroll()) and payload_json (the raw request that
    # produced it) describe the SAME payment. Pulling list-shaped keys from
    # both, as this used to do, summed each contractor's pay twice. Only the
    # payload is inspected when a run genuinely has no results yet.
    candidates: list[Any] = _pull(results) if results else _pull(payload)
    if not candidates:
        for key in (
            "contractors_json",
            "results_json",
            "settlements_json",
        ):
            parsed_list = _coalesce_list(row.get(key))
            if parsed_list:
                candidates.extend(parsed_list)

    normalized: list[dict[str, Any]] = []
    for item in candidates:
        if isinstance(item, dict):
            normalized.append(item)
    return normalized


def _resolve_contractor_identifier(item: dict[str, Any]) -> str | None:
    for key in (
        "contractor_id",
        "worker_id",
        "driver_id",
        "contractor_uuid",
        "external_id",
        "id",
    ):
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _resolve_nec_amount(item: dict[str, Any]) -> Decimal:
    explicit_keys = (
        "nonemployee_compensation",
        "nec_amount",
        "reportable_amount",
        "taxable_compensation",
        "gross",
        "gross_pay",
        "total_gross",
    )
    for key in explicit_keys:
        value = item.get(key)
        if value not in (None, "", []):
            return _safe_decimal(value)

    base_gross = _safe_decimal(item.get("base_gross"))
    accessorials = _sum_nested_amounts(item.get("accessorials"))
    if base_gross or accessorials:
        return (base_gross + accessorials).quantize(TWOPLACES)

    net = _safe_decimal(item.get("net"))
    if net:
        return net

    return Decimal("0.00")


def _resolve_reimbursements(item: dict[str, Any]) -> Decimal:
    direct = item.get("reimbursements")
    if direct not in (None, "", []):
        return _sum_nested_amounts(direct)

    total = Decimal("0.00")
    for key in ("fuel_reimbursement", "lumper_reimbursement", "tolls_reimbursement"):
        total += _safe_decimal(item.get(key))
    return total.quantize(TWOPLACES)


def _resolve_deductions(item: dict[str, Any]) -> Decimal:
    direct = item.get("deductions")
    if direct not in (None, "", []):
        return _sum_nested_amounts(direct)

    total = Decimal("0.00")
    for key in ("insurance", "escrow", "chargebacks", "advances"):
        total += _safe_decimal(item.get(key))
    return total.quantize(TWOPLACES)


def _csv_safe(value: Any) -> str:
    if value is None:
        return ""
    text_value = str(value)
    if text_value[:1] in ("=", "+", "-", "@"):
        return "'" + text_value
    return text_value


def _fetch_payroll_runs(company_id: int, year: int) -> list[dict[str, Any]]:
    # payroll_runs has no "id" column — its primary key is run_id (a UUID
    # string, per migrations/versions/20260401_payroll_runs.py), so ordering
    # by it wouldn't be chronological anyway. created_at is the real
    # timestamp column.
    query = text(
        """
        SELECT *
        FROM payroll_runs
        WHERE company_id = :company_id
        ORDER BY created_at DESC
        """
    )
    rows = db.session.execute(query, {"company_id": company_id}).mappings().all()

    filtered: list[dict[str, Any]] = []
    for row in rows:
        row_dict = dict(row)
        status_value = str(row_dict.get("status") or "").strip().lower()
        if status_value and status_value not in {"executed", "finalized", "completed", "paid"}:
            continue

        run_date = _extract_run_date(row_dict)
        if run_date is None:
            continue
        if run_date.year != year:
            continue

        filtered.append(row_dict)

    return filtered


def _build_1099_summary(company_id: int, year: int) -> dict[str, Any]:
    rows = _fetch_payroll_runs(company_id, year)

    aggregates: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "contractor_key": None,
            "contractor_id": None,
            "legal_name": None,
            "business_name": None,
            "email": None,
            "phone": None,
            "address_line1": None,
            "address_line2": None,
            "city": None,
            "state": None,
            "postal_code": None,
            "country": None,
            "tin_last4": None,
            "tax_classification": None,
            "w9_received": False,
            "w9_received_at": None,
            "nec_total": Decimal("0.00"),
            "reimbursements_total": Decimal("0.00"),
            "deductions_total": Decimal("0.00"),
            "run_count": 0,
            "source_run_ids": [],
        }
    )

    numeric_contractor_ids: set[int] = set()

    for row in rows:
        run_id = row.get("id")
        items = _extract_candidate_lists(row)

        for item in items:
            contractor_key = _resolve_contractor_identifier(item)
            if not contractor_key:
                continue

            nec_amount = _resolve_nec_amount(item)
            reimbursements = _resolve_reimbursements(item)
            deductions = _resolve_deductions(item)

            bucket = aggregates[contractor_key]
            bucket["contractor_key"] = contractor_key
            bucket["nec_total"] += nec_amount
            bucket["reimbursements_total"] += reimbursements
            bucket["deductions_total"] += deductions
            bucket["run_count"] += 1

            if run_id is not None and run_id not in bucket["source_run_ids"]:
                bucket["source_run_ids"].append(run_id)

            numeric_id = _safe_int(contractor_key)
            if numeric_id is not None:
                bucket["contractor_id"] = numeric_id
                numeric_contractor_ids.add(numeric_id)

    contractor_map: dict[int, Contractor] = {}
    if numeric_contractor_ids:
        contractors = Contractor.query.filter(
            Contractor.company_id == company_id,
            Contractor.id.in_(numeric_contractor_ids),
        ).all()
        contractor_map = {contractor.id: contractor for contractor in contractors}

    summary_rows: list[dict[str, Any]] = []
    for contractor_key, bucket in aggregates.items():
        contractor_id = bucket["contractor_id"]
        contractor = contractor_map.get(contractor_id) if contractor_id is not None else None

        if contractor is not None:
            bucket["legal_name"] = contractor.legal_name
            bucket["business_name"] = contractor.business_name
            bucket["email"] = contractor.email
            bucket["phone"] = contractor.phone
            bucket["address_line1"] = contractor.address_line1
            bucket["address_line2"] = contractor.address_line2
            bucket["city"] = contractor.city
            bucket["state"] = contractor.state
            bucket["postal_code"] = contractor.postal_code
            bucket["country"] = contractor.country
            bucket["tin_last4"] = contractor.tin_last4
            bucket["tax_classification"] = contractor.tax_classification
            bucket["w9_received"] = bool(contractor.w9_received)
            bucket["w9_received_at"] = (
                contractor.w9_received_at.isoformat() if contractor.w9_received_at else None
            )
        else:
            bucket["legal_name"] = bucket["legal_name"] or f"Contractor {contractor_key}"

        summary_rows.append(
            {
                "contractor_key": contractor_key,
                "contractor_id": contractor_id,
                "legal_name": bucket["legal_name"],
                "business_name": bucket["business_name"],
                "email": bucket["email"],
                "phone": bucket["phone"],
                "address_line1": bucket["address_line1"],
                "address_line2": bucket["address_line2"],
                "city": bucket["city"],
                "state": bucket["state"],
                "postal_code": bucket["postal_code"],
                "country": bucket["country"],
                "tin_last4": bucket["tin_last4"],
                "tax_classification": bucket["tax_classification"],
                "w9_received": bucket["w9_received"],
                "w9_received_at": bucket["w9_received_at"],
                "nec_total": format(bucket["nec_total"].quantize(TWOPLACES), ".2f"),
                "reimbursements_total": format(
                    bucket["reimbursements_total"].quantize(TWOPLACES), ".2f"
                ),
                "deductions_total": format(
                    bucket["deductions_total"].quantize(TWOPLACES), ".2f"
                ),
                "run_count": bucket["run_count"],
                "source_run_ids": bucket["source_run_ids"],
                "threshold_met": bucket["nec_total"] >= Decimal("600.00"),
            }
        )

    summary_rows.sort(key=lambda x: (Decimal(x["nec_total"]), x["legal_name"] or ""), reverse=True)

    nec_total_all = sum((Decimal(row["nec_total"]) for row in summary_rows), Decimal("0.00"))

    return {
        "year": year,
        "company_id": company_id,
        "generated_at": _utc_now_iso(),
        "contractor_count": len(summary_rows),
        "nec_total_all": format(nec_total_all.quantize(TWOPLACES), ".2f"),
        "contractors": summary_rows,
    }


@tax_1099_bp.get("/summary")
def get_1099_summary():
    auth, auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        year = _parse_year(request.args.get("year"))
        summary = _build_1099_summary(auth["company_id"], year)
        return jsonify(summary), 200
    except ValueError as exc:
        return _json_error(str(exc), 400, "VALIDATION_ERROR")
    except Exception as exc:
        return jsonify(
            {
                "error": "SUMMARY_BUILD_FAILED",
                "message": "Failed to build 1099 summary",
                "detail": str(exc),
            }
        ), 500


@tax_1099_bp.get("/export.csv")
def export_1099_csv():
    auth, auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        year = _parse_year(request.args.get("year"))
        summary = _build_1099_summary(auth["company_id"], year)

        buffer = io.StringIO()
        writer = csv.writer(buffer)

        writer.writerow(
            [
                "year",
                "company_id",
                "contractor_id",
                "contractor_key",
                "legal_name",
                "business_name",
                "email",
                "phone",
                "address_line1",
                "address_line2",
                "city",
                "state",
                "postal_code",
                "country",
                "tax_classification",
                "tin_last4",
                "w9_received",
                "w9_received_at",
                "nec_total",
                "reimbursements_total",
                "deductions_total",
                "run_count",
                "threshold_met",
                "source_run_ids",
            ]
        )

        for row in summary["contractors"]:
            writer.writerow(
                [
                    _csv_safe(summary["year"]),
                    _csv_safe(summary["company_id"]),
                    _csv_safe(row["contractor_id"]),
                    _csv_safe(row["contractor_key"]),
                    _csv_safe(row["legal_name"]),
                    _csv_safe(row["business_name"]),
                    _csv_safe(row["email"]),
                    _csv_safe(row["phone"]),
                    _csv_safe(row["address_line1"]),
                    _csv_safe(row["address_line2"]),
                    _csv_safe(row["city"]),
                    _csv_safe(row["state"]),
                    _csv_safe(row["postal_code"]),
                    _csv_safe(row["country"]),
                    _csv_safe(row["tax_classification"]),
                    _csv_safe(row["tin_last4"]),
                    _csv_safe(row["w9_received"]),
                    _csv_safe(row["w9_received_at"]),
                    _csv_safe(row["nec_total"]),
                    _csv_safe(row["reimbursements_total"]),
                    _csv_safe(row["deductions_total"]),
                    _csv_safe(row["run_count"]),
                    _csv_safe(row["threshold_met"]),
                    _csv_safe(",".join(str(x) for x in row["source_run_ids"])),
                ]
            )

        csv_data = buffer.getvalue()
        buffer.close()

        filename = f"1099_nec_summary_{auth['company_id']}_{year}.csv"
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )
    except ValueError as exc:
        return _json_error(str(exc), 400, "VALIDATION_ERROR")
    except Exception as exc:
        return jsonify(
            {
                "error": "CSV_EXPORT_FAILED",
                "message": "Failed to export 1099 CSV",
                "detail": str(exc),
            }
        ), 500

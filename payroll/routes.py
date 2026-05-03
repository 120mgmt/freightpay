# File: payroll/routes.py
# Purpose: Enterprise-grade payroll routes with contractor linkage, tenant isolation,
#          reconciliation validation, provider submission capture, and audit-safe behavior.

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from typing import Any

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from sqlalchemy.exc import SQLAlchemyError

from db import db
from models.contractor import Contractor
from models.payroll_run import PayrollRun


payroll_bp = Blueprint("payroll_bp", __name__, url_prefix="/payroll")
provider_submit_bp = Blueprint(
    "provider_submit_bp",
    __name__,
    url_prefix="/payroll/provider",
)

TWOPLACES = Decimal("0.01")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


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


def _safe_decimal(value: Any, field_name: str) -> Decimal:
    try:
        return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid numeric value for {field_name}")


def _serialize_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def _safe_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        text_value = value.strip()
        if not text_value:
            return None
        try:
            return json.loads(text_value)
        except json.JSONDecodeError:
            return value
    return value


def _serialize_contractor(contractor: Contractor) -> dict[str, Any]:
    return {
        "id": contractor.id,
        "company_id": contractor.company_id,
        "legal_name": contractor.legal_name,
        "business_name": contractor.business_name,
        "display_name": contractor.display_name,
        "effective_name": contractor.effective_name,
        "email": contractor.email,
        "phone": contractor.phone,
        "is_active": contractor.is_active,
        "w9_received": contractor.w9_received,
        "tax_classification": contractor.tax_classification,
    }


def _serialize_payroll_run(run: PayrollRun) -> dict[str, Any]:
    payload = _safe_json(getattr(run, "payload_json", None) or getattr(run, "payload", None))
    results = _safe_json(getattr(run, "results_json", None) or getattr(run, "results", None))
    provider_payload = _safe_json(
        getattr(run, "provider_payload_json", None) or getattr(run, "provider_payload", None)
    )
    provider_response = _safe_json(
        getattr(run, "provider_response_json", None) or getattr(run, "provider_response", None)
    )

    data = {
        "id": getattr(run, "id", None),
        "company_id": getattr(run, "company_id", None),
        "status": getattr(run, "status", None),
        "provider_name": getattr(run, "provider_name", None),
        "provider_run_id": getattr(run, "provider_run_id", None),
        "period_start": _serialize_datetime(getattr(run, "period_start", None)),
        "period_end": _serialize_datetime(getattr(run, "period_end", None)),
        "pay_date": _serialize_datetime(getattr(run, "pay_date", None)),
        "created_at": _serialize_datetime(getattr(run, "created_at", None)),
        "updated_at": _serialize_datetime(getattr(run, "updated_at", None)),
        "submitted_at": _serialize_datetime(getattr(run, "submitted_at", None)),
        "completed_at": _serialize_datetime(getattr(run, "completed_at", None)),
        "created_by_user_id": getattr(run, "created_by_user_id", None),
        "updated_by_user_id": getattr(run, "updated_by_user_id", None),
        "payload": payload,
        "results": results,
        "provider_payload": provider_payload,
        "provider_response": provider_response,
    }

    if hasattr(run, "gross_total"):
        data["gross_total"] = str(getattr(run, "gross_total"))
    if hasattr(run, "reimbursements_total"):
        data["reimbursements_total"] = str(getattr(run, "reimbursements_total"))
    if hasattr(run, "deductions_total"):
        data["deductions_total"] = str(getattr(run, "deductions_total"))
    if hasattr(run, "net_total"):
        data["net_total"] = str(getattr(run, "net_total"))

    return data


def _set_if_present(obj: Any, field_name: str, value: Any) -> None:
    if hasattr(obj, field_name):
        setattr(obj, field_name, value)


def _normalize_period_date(raw: Any, field_name: str) -> datetime:
    if raw is None:
        raise ValueError(f"{field_name} is required")

    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw
        return raw.astimezone(timezone.utc).replace(tzinfo=None)

    raw_value = str(raw).strip()
    if not raw_value:
        raise ValueError(f"{field_name} is required")

    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(raw_value, fmt)
        except ValueError:
            continue

    try:
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        raise ValueError(f"{field_name} must be a valid ISO date or datetime")


def _require_payload(required_fields: list[str], payload: dict[str, Any]) -> None:
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(f"Missing fields: {missing}")


def _extract_contractors_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    contractors = payload.get("contractors")
    if contractors is None:
        raise ValueError("contractors is required")
    if not isinstance(contractors, list) or not contractors:
        raise ValueError("contractors must be a non-empty list")

    normalized: list[dict[str, Any]] = []

    for index, item in enumerate(contractors):
        if not isinstance(item, dict):
            raise ValueError(f"contractors[{index}] must be an object")

        contractor_id = item.get("contractor_id")
        try:
            contractor_id = int(contractor_id)
        except (TypeError, ValueError):
            raise ValueError(f"contractors[{index}].contractor_id must be an integer")

        gross = _safe_decimal(item.get("gross", "0"), f"contractors[{index}].gross")
        reimbursements = _safe_decimal(
            item.get("reimbursements", "0"),
            f"contractors[{index}].reimbursements",
        )
        deductions = _safe_decimal(
            item.get("deductions", "0"),
            f"contractors[{index}].deductions",
        )
        net = _safe_decimal(item.get("net", "0"), f"contractors[{index}].net")

        if gross < 0:
            raise ValueError(f"contractors[{index}].gross cannot be negative")
        if reimbursements < 0:
            raise ValueError(f"contractors[{index}].reimbursements cannot be negative")
        if deductions < 0:
            raise ValueError(f"contractors[{index}].deductions cannot be negative")
        if net < 0:
            raise ValueError(f"contractors[{index}].net cannot be negative")

        expected_net = (gross + reimbursements - deductions).quantize(
            TWOPLACES,
            rounding=ROUND_HALF_UP,
        )
        if expected_net != net:
            raise ValueError(
                f"contractors[{index}].net does not reconcile with gross + reimbursements - deductions"
            )

        normalized.append(
            {
                "contractor_id": contractor_id,
                "gross": gross,
                "reimbursements": reimbursements,
                "deductions": deductions,
                "net": net,
                "notes": item.get("notes"),
            }
        )

    return normalized


def _load_company_contractors(company_id: int, contractor_ids: list[int]) -> dict[int, Contractor]:
    rows = Contractor.query.filter(
        Contractor.company_id == company_id,
        Contractor.id.in_(contractor_ids),
        Contractor.is_active.is_(True),
    ).all()

    mapping = {row.id: row for row in rows}
    missing = sorted(set(contractor_ids) - set(mapping.keys()))
    if missing:
        raise LookupError(f"Contractors not found or inactive for company: {missing}")
    return mapping


def _build_run_payload(
    contractor_rows: list[dict[str, Any]],
    contractor_map: dict[int, Contractor],
) -> dict[str, Any]:
    contractor_payload: list[dict[str, Any]] = []

    gross_total = Decimal("0.00")
    reimbursements_total = Decimal("0.00")
    deductions_total = Decimal("0.00")
    net_total = Decimal("0.00")

    for row in contractor_rows:
        contractor = contractor_map[row["contractor_id"]]

        contractor_payload.append(
            {
                "contractor_id": contractor.id,
                "contractor_name": contractor.effective_name,
                "legal_name": contractor.legal_name,
                "gross": str(row["gross"]),
                "reimbursements": str(row["reimbursements"]),
                "deductions": str(row["deductions"]),
                "net": str(row["net"]),
                "notes": row.get("notes"),
                "w9_received": contractor.w9_received,
                "tax_classification": contractor.tax_classification,
            }
        )

        gross_total += row["gross"]
        reimbursements_total += row["reimbursements"]
        deductions_total += row["deductions"]
        net_total += row["net"]

    return {
        "contractors": contractor_payload,
        "gross_total": str(gross_total.quantize(TWOPLACES)),
        "reimbursements_total": str(reimbursements_total.quantize(TWOPLACES)),
        "deductions_total": str(deductions_total.quantize(TWOPLACES)),
        "net_total": str(net_total.quantize(TWOPLACES)),
    }


@payroll_bp.get("/health")
def payroll_health():
    return jsonify({"status": "ok", "timestamp": _utc_now_iso()}), 200


@payroll_bp.post("/runs")
def create_payroll_run():
    auth, auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        payload = request.get_json(force=True) or {}

        _require_payload(
            ["period_start", "period_end", "pay_date", "contractors"],
            payload,
        )

        period_start = _normalize_period_date(payload.get("period_start"), "period_start")
        period_end = _normalize_period_date(payload.get("period_end"), "period_end")
        pay_date = _normalize_period_date(payload.get("pay_date"), "pay_date")

        if period_end < period_start:
            return _json_error("period_end cannot be earlier than period_start")

        contractors = _extract_contractors_from_payload(payload)
        contractor_ids = [row["contractor_id"] for row in contractors]
        contractor_map = _load_company_contractors(auth["company_id"], contractor_ids)

        run_payload = _build_run_payload(contractors, contractor_map)

        payroll_run = PayrollRun()

        _set_if_present(payroll_run, "company_id", auth["company_id"])
        _set_if_present(payroll_run, "status", "draft")
        _set_if_present(payroll_run, "provider_name", payload.get("provider_name") or None)
        _set_if_present(payroll_run, "period_start", period_start)
        _set_if_present(payroll_run, "period_end", period_end)
        _set_if_present(payroll_run, "pay_date", pay_date)
        _set_if_present(payroll_run, "created_by_user_id", auth["user_id"])
        _set_if_present(payroll_run, "updated_by_user_id", auth["user_id"])
        _set_if_present(payroll_run, "payload_json", json.dumps(run_payload, separators=(",", ":")))
        _set_if_present(payroll_run, "payload", json.dumps(run_payload, separators=(",", ":")))
        _set_if_present(payroll_run, "gross_total", Decimal(run_payload["gross_total"]))
        _set_if_present(
            payroll_run,
            "reimbursements_total",
            Decimal(run_payload["reimbursements_total"]),
        )
        _set_if_present(
            payroll_run,
            "deductions_total",
            Decimal(run_payload["deductions_total"]),
        )
        _set_if_present(payroll_run, "net_total", Decimal(run_payload["net_total"]))

        db.session.add(payroll_run)
        db.session.commit()

        return jsonify({"run": _serialize_payroll_run(payroll_run)}), 201

    except ValueError as exc:
        return _json_error(str(exc), 400, "VALIDATION_ERROR")
    except LookupError as exc:
        return _json_error(str(exc), 404, "NOT_FOUND")
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify(
            {
                "error": "DATABASE_ERROR",
                "message": "Failed to create payroll run",
                "detail": str(exc),
            }
        ), 500
    except Exception as exc:
        db.session.rollback()
        return jsonify(
            {
                "error": "PAYROLL_RUN_CREATE_FAILED",
                "message": "Unexpected error while creating payroll run",
                "detail": str(exc),
            }
        ), 500


@payroll_bp.get("/runs")
def list_payroll_runs():
    auth, auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        query = PayrollRun.query

        if hasattr(PayrollRun, "company_id"):
            query = query.filter(PayrollRun.company_id == auth["company_id"])

        status_filter = request.args.get("status")
        if status_filter and hasattr(PayrollRun, "status"):
            query = query.filter(PayrollRun.status == status_filter.strip())

        if hasattr(PayrollRun, "id"):
            query = query.order_by(PayrollRun.id.desc())

        runs = query.all()
        return jsonify({"runs": [_serialize_payroll_run(run) for run in runs]}), 200

    except Exception as exc:
        return jsonify(
            {
                "error": "PAYROLL_RUN_LIST_FAILED",
                "message": "Failed to list payroll runs",
                "detail": str(exc),
            }
        ), 500


@payroll_bp.get("/runs/<int:run_id>")
def get_payroll_run(run_id: int):
    auth, auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        run = PayrollRun.query.get(run_id)
        if not run:
            return _json_error("Payroll run not found", 404, "NOT_FOUND")

        if hasattr(run, "company_id") and int(getattr(run, "company_id")) != auth["company_id"]:
            return _json_error("Payroll run not found for this company", 404, "NOT_FOUND")

        return jsonify({"run": _serialize_payroll_run(run)}), 200

    except Exception as exc:
        return jsonify(
            {
                "error": "PAYROLL_RUN_FETCH_FAILED",
                "message": "Failed to fetch payroll run",
                "detail": str(exc),
            }
        ), 500


@payroll_bp.get("/contractors/<int:contractor_id>/year-to-date")
def contractor_year_to_date(contractor_id: int):
    auth, auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        contractor = Contractor.query.filter_by(
            id=contractor_id,
            company_id=auth["company_id"],
            is_active=True,
        ).first()

        if not contractor:
            return _json_error("Contractor not found", 404, "NOT_FOUND")

        year = request.args.get("year")
        if year is None:
            target_year = datetime.now(timezone.utc).year
        else:
            try:
                target_year = int(str(year).strip())
            except (TypeError, ValueError):
                return _json_error("year must be a valid integer", 400, "VALIDATION_ERROR")

        query = PayrollRun.query
        if hasattr(PayrollRun, "company_id"):
            query = query.filter(PayrollRun.company_id == auth["company_id"])

        runs = query.all()

        gross_total = Decimal("0.00")
        reimbursements_total = Decimal("0.00")
        deductions_total = Decimal("0.00")
        net_total = Decimal("0.00")
        run_ids: list[int] = []

        for run in runs:
            pay_date = getattr(run, "pay_date", None)
            if isinstance(pay_date, datetime):
                run_year = pay_date.year
            elif pay_date:
                try:
                    run_year = datetime.fromisoformat(str(pay_date).replace("Z", "+00:00")).year
                except ValueError:
                    continue
            else:
                continue

            if run_year != target_year:
                continue

            payload = _safe_json(getattr(run, "payload_json", None) or getattr(run, "payload", None))
            if not isinstance(payload, dict):
                continue

            contractors = payload.get("contractors")
            if not isinstance(contractors, list):
                continue

            for item in contractors:
                if not isinstance(item, dict):
                    continue
                if int(item.get("contractor_id", 0)) != contractor_id:
                    continue

                gross_total += _safe_decimal(item.get("gross", "0"), "gross")
                reimbursements_total += _safe_decimal(
                    item.get("reimbursements", "0"),
                    "reimbursements",
                )
                deductions_total += _safe_decimal(item.get("deductions", "0"), "deductions")
                net_total += _safe_decimal(item.get("net", "0"), "net")

                if getattr(run, "id", None) is not None:
                    run_ids.append(int(run.id))

        return jsonify(
            {
                "contractor": _serialize_contractor(contractor),
                "year": target_year,
                "gross_total": str(gross_total.quantize(TWOPLACES)),
                "reimbursements_total": str(reimbursements_total.quantize(TWOPLACES)),
                "deductions_total": str(deductions_total.quantize(TWOPLACES)),
                "net_total": str(net_total.quantize(TWOPLACES)),
                "run_ids": sorted(set(run_ids)),
            }
        ), 200

    except Exception as exc:
        return jsonify(
            {
                "error": "YTD_FETCH_FAILED",
                "message": "Failed to calculate contractor year-to-date totals",
                "detail": str(exc),
            }
        ), 500


@provider_submit_bp.post("/submit")
def provider_submit():
    auth, auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        payload = request.get_json(force=True) or {}

        try:
            run_id = int(payload.get("run_id"))
        except (TypeError, ValueError):
            return _json_error("run_id must be a valid integer", 400, "VALIDATION_ERROR")

        run = PayrollRun.query.get(run_id)
        if not run:
            return _json_error("Payroll run not found", 404, "NOT_FOUND")

        if hasattr(run, "company_id") and int(getattr(run, "company_id")) != auth["company_id"]:
            return _json_error("Payroll run not found for this company", 404, "NOT_FOUND")

        provider_name = str(payload.get("provider_name") or "").strip().lower()
        if not provider_name:
            return _json_error("provider_name is required", 400, "VALIDATION_ERROR")

        provider_payload = payload.get("provider_payload") or {}
        if not isinstance(provider_payload, dict):
            return _json_error("provider_payload must be an object", 400, "VALIDATION_ERROR")

        _set_if_present(run, "provider_name", provider_name)
        _set_if_present(run, "provider_payload_json", json.dumps(provider_payload, separators=(",", ":")))
        _set_if_present(run, "provider_payload", json.dumps(provider_payload, separators=(",", ":")))
        _set_if_present(run, "status", "submitted")
        _set_if_present(run, "submitted_at", _utc_now().replace(tzinfo=None))
        _set_if_present(run, "updated_by_user_id", auth["user_id"])

        provider_response = {
            "accepted": True,
            "provider_name": provider_name,
            "submitted_at": _utc_now_iso(),
            "mode": "captured",
        }
        _set_if_present(run, "provider_response_json", json.dumps(provider_response, separators=(",", ":")))
        _set_if_present(run, "provider_response", json.dumps(provider_response, separators=(",", ":")))

        db.session.commit()

        return jsonify(
            {
                "run": _serialize_payroll_run(run),
                "provider_submission": provider_response,
            }
        ), 200

    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify(
            {
                "error": "DATABASE_ERROR",
                "message": "Failed to submit payroll run to provider",
                "detail": str(exc),
            }
        ), 500
    except Exception as exc:
        db.session.rollback()
        return jsonify(
            {
                "error": "PROVIDER_SUBMIT_FAILED",
                "message": "Unexpected error while submitting payroll run",
                "detail": str(exc),
            }
        ), 500

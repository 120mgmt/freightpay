# File: services/post_journal.py
# Purpose: Post immutable double-entry journals + ledger entries
# Status: Enterprise hardened
# Date: 2026-03-08

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select

from db import db
from models.chart_of_accounts import Account
from models.ledger import Journal, LedgerEntry


def _to_decimal(value: Any) -> Decimal:
    try:
        if value is None:
            return Decimal("0.00")
        if isinstance(value, Decimal):
            return value.quantize(Decimal("0.01"))
        text_value = str(value).strip()
        if not text_value:
            return Decimal("0.00")
        return Decimal(text_value).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Invalid amount (must be numeric)") from exc


def _as_str(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _require_int(value: Any, field: str) -> int:
    text_value = _as_str(value)
    if not text_value:
        raise ValueError(f"Missing required field: {field}")
    try:
        parsed = int(text_value)
    except Exception as exc:
        raise ValueError(f"Invalid {field} (must be integer)") from exc
    if parsed <= 0:
        raise ValueError(f"Invalid {field} (must be positive integer)")
    return parsed


def _require_nonempty(value: Any, field: str) -> str:
    text_value = _as_str(value)
    if not text_value:
        raise ValueError(f"Missing required field: {field}")
    return text_value


def _normalize_period(value: Any) -> str:
    period = _as_str(value)
    if len(period) != 7 or period[4] != "-":
        raise ValueError("Invalid accounting_period (must be YYYY-MM)")
    year, month = period.split("-", 1)
    if not (year.isdigit() and month.isdigit()):
        raise ValueError("Invalid accounting_period (must be YYYY-MM)")
    month_int = int(month)
    if month_int < 1 or month_int > 12:
        raise ValueError("Invalid accounting_period month")
    return f"{int(year):04d}-{month_int:02d}"


def post_journal(
    *,
    company_id: int,
    source_type: str,
    source_id: str,
    accounting_period: str,
    description: str,
    posted_by: int | None,
    lines: list[dict[str, Any]],
) -> dict[str, Any]:

    company_id = _require_int(company_id, "company_id")
    source_type = _require_nonempty(source_type, "source_type")
    source_id = _require_nonempty(source_id, "source_id")
    accounting_period = _normalize_period(accounting_period)
    description = _require_nonempty(description, "description")
    posted_by_id = None if posted_by in (None, "") else _require_int(posted_by, "posted_by")

    if not isinstance(lines, list) or not lines:
        raise ValueError("lines must be a non-empty list")

    normalized_lines: list[dict[str, Any]] = []
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")

    for index, line in enumerate(lines):

        if not isinstance(line, dict):
            raise ValueError(f"Invalid line at index {index} (must be object)")

        account_code = _require_nonempty(line.get("account_code"), f"account_code on line {index}")
        debit = _to_decimal(line.get("debit"))
        credit = _to_decimal(line.get("credit"))

        if debit < 0 or credit < 0:
            raise ValueError(f"Negative amounts not allowed (line {index})")

        if (debit > 0 and credit > 0) or (debit == 0 and credit == 0):
            raise ValueError(f"Each line must have exactly one of debit or credit > 0 (line {index})")

        memo = _as_str(line.get("memo") or line.get("description") or "")

        normalized_lines.append(
            {
                "account_code": account_code,
                "debit": debit,
                "credit": credit,
                "memo": memo or None,
            }
        )

        total_debit += debit
        total_credit += credit

    if total_debit != total_credit:
        raise ValueError("Journal not balanced (total debit must equal total credit)")

    account_codes = sorted({line["account_code"] for line in normalized_lines})

    account_rows = db.session.execute(
        select(Account)
        .where(Account.company_id == company_id)
        .where(Account.account_code.in_(account_codes))
    ).scalars().all()

    account_map = {account.account_code: account for account in account_rows}

    missing_codes = [code for code in account_codes if code not in account_map]
    if missing_codes:
        raise ValueError(f"Unknown account_code(s): {', '.join(missing_codes)}")

    inactive_codes = [code for code in account_codes if not bool(account_map[code].is_active)]
    if inactive_codes:
        raise ValueError(f"Inactive account_code(s): {', '.join(inactive_codes)}")

    with db.session.begin():

        journal = Journal(
            company_id=company_id,
            source_type=source_type,
            source_id=source_id,
            accounting_period=accounting_period,
            description=description,
            posted_by=posted_by_id,
        )

        db.session.add(journal)
        db.session.flush()

        for line in normalized_lines:

            account = account_map[line["account_code"]]

            db.session.add(
                LedgerEntry(
                    company_id=company_id,
                    journal_id=journal.id,
                    account_id=account.id,
                    account_code=account.account_code,
                    debit=line["debit"],
                    credit=line["credit"],
                    memo=line["memo"],
                )
            )

    return {
        "status": "posted",
        "company_id": company_id,
        "journal_id": int(journal.id),
        "accounting_period": journal.accounting_period,
        "source_type": journal.source_type,
        "source_id": journal.source_id,
        "total_debit": str(total_debit),
        "total_credit": str(total_credit),
        "line_count": len(normalized_lines),
    }

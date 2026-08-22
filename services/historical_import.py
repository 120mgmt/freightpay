# File: services/historical_import.py
# Purpose: Parse a user-supplied CSV of past income/expense records so they can
# be reviewed and posted as manual bookkeeping transactions (see routes/coa.py
# /coa/import/preview and /coa/import/commit). Pure parsing — no DB access.

from __future__ import annotations

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

MAX_ROWS = 2000

_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y")


def _parse_date(raw: str) -> str | None:
    raw = (raw or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_amount(raw: str) -> Decimal | None:
    raw = (raw or "").strip().replace("$", "").replace(",", "")
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _infer_type(raw_type: str, amount: Decimal) -> str | None:
    t = (raw_type or "").strip().lower()
    if t in ("expense", "debit", "d", "out"):
        return "expense"
    if t in ("income", "credit", "c", "in", "revenue"):
        return "income"
    if t:
        return None
    # No explicit type column — infer from the sign of the amount.
    if amount < 0:
        return "expense"
    if amount > 0:
        return "income"
    return None


def parse_import_csv(csv_bytes: bytes) -> dict[str, Any]:
    """
    Parses a CSV of historical transactions into normalized rows.

    Expected columns (case-insensitive, extra columns ignored):
      date         required — YYYY-MM-DD or MM/DD/YYYY
      description  required
      amount       required — a positive or negative number
      type         optional — "expense" or "income"; inferred from the
                   amount's sign when omitted
      category     optional — an account name to match against the
                   company's chart of accounts (resolved by the caller)
      vendor       optional

    Returns {"rows": [...], "error": str | None}. Never raises — a malformed
    file surfaces as a top-level error string, and per-row problems surface
    as that row's own "error" field so the caller can still edit and import
    the rows that did parse.
    """
    if not csv_bytes:
        return {"rows": [], "error": "The file is empty."}

    try:
        text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {"rows": [], "error": "Could not read the file as text (expected a CSV)."}

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return {"rows": [], "error": "The CSV has no header row."}

    header_map = {h.strip().lower(): h for h in reader.fieldnames}
    missing = [c for c in ("date", "description", "amount") if c not in header_map]
    if missing:
        return {
            "rows": [],
            "error": f"Missing required column(s): {', '.join(missing)}. "
            "Expected columns: date, description, amount, and optionally type, category, vendor.",
        }

    def _get(row: dict, col: str) -> str:
        key = header_map.get(col)
        return (row.get(key) or "").strip() if key else ""

    rows: list[dict[str, Any]] = []
    for i, raw_row in enumerate(reader):
        if len(rows) >= MAX_ROWS:
            return {
                "rows": rows,
                "error": f"Only the first {MAX_ROWS} rows were read; split larger files up.",
            }

        row_index = i + 1
        date_raw = _get(raw_row, "date")
        amount_raw = _get(raw_row, "amount")
        description = _get(raw_row, "description")

        date_iso = _parse_date(date_raw)
        amount = _parse_amount(amount_raw)

        error = None
        if not date_iso:
            error = f"Unrecognized date: '{date_raw}'"
        elif amount is None:
            error = f"Unrecognized amount: '{amount_raw}'"
        elif amount == 0:
            error = "Amount cannot be zero"
        elif not description:
            error = "Description is required"

        txn_type = None
        if not error:
            txn_type = _infer_type(_get(raw_row, "type"), amount)
            if not txn_type:
                error = f"Unrecognized type: '{_get(raw_row, 'type')}' (use expense or income)"

        rows.append(
            {
                "row_index": row_index,
                "date": date_iso,
                "description": description or None,
                "amount": str(abs(amount)) if amount is not None else None,
                "type": txn_type,
                "category_text": _get(raw_row, "category") or None,
                "vendor": _get(raw_row, "vendor") or None,
                "error": error,
            }
        )

    if not rows:
        return {"rows": [], "error": "No data rows found in the file."}

    return {"rows": rows, "error": None}

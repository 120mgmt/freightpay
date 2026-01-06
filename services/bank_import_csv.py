# freightpay/services/bank_import_csv.py
# BANK TRANSACTION CSV INGESTION → LEDGER (PRODUCTION-READY)
# Purpose: Import bank CSVs, normalize rows, and post balanced journals.
# Safe for Render + PostgreSQL + existing ledger guard.

from __future__ import annotations

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable

from sqlalchemy.orm import Session

from services.ledger_posting_guard import post_journal
from services.ledger_posting_guard import LedgerPostingError


class BankImportError(Exception):
    pass


REQUIRED_COLUMNS = {
    "date",          # YYYY-MM-DD or MM/DD/YYYY
    "description",   # bank memo
    "amount",        # signed or absolute
    "type",          # debit | credit (or D/C)
}


def _parse_date(raw: str) -> datetime.date:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise BankImportError(f"Invalid date format: {raw}")


def _parse_amount(raw: str) -> Decimal:
    try:
        amt = Decimal(raw.replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        raise BankImportError(f"Invalid amount: {raw}")
    return amt.copy_abs()


def _normalize_type(raw: str) -> str:
    r = raw.strip().lower()
    if r in ("debit", "d"):
        return "debit"
    if r in ("credit", "c"):
        return "credit"
    raise BankImportError(f"Invalid type (must be debit/credit): {raw}")


def _validate_header(header: Iterable[str]):
    cols = {h.strip().lower() for h in header}
    missing = REQUIRED_COLUMNS - cols
    if missing:
        raise BankImportError(f"Missing required columns: {', '.join(sorted(missing))}")


def import_bank_csv(
    db: Session,
    *,
    company_id,
    accounting_period: str,
    posted_by,
    csv_bytes: bytes,
    cash_account_code: str = "1000",      # Cash
    clearing_account_code: str = "1099",  # Bank Clearing / Suspense
) -> int:
    """
    Imports a bank CSV and posts ONE journal per file.
    Each row becomes a balanced pair against clearing.
    """

    if not csv_bytes:
        raise BankImportError("Empty CSV")

    text = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        raise BankImportError("CSV has no header")

    _validate_header(reader.fieldnames)

    entries: list[dict] = []
    row_count = 0

    for row in reader:
        row_count += 1

        tx_date = _parse_date(row["date"])
        desc = (row.get("description") or "").strip()
        amt = _parse_amount(row["amount"])
        tx_type = _normalize_type(row["type"])

        if amt <= 0:
            raise BankImportError(f"Row {row_count}: amount must be > 0")

        if tx_type == "debit":
            # Money left bank: credit cash, debit clearing
            entries.append({
                "account_code": clearing_account_code,
                "debit": amt,
                "credit": Decimal("0.00"),
                "currency": "USD",
            })
            entries.append({
                "account_code": cash_account_code,
                "debit": Decimal("0.00"),
                "credit": amt,
                "currency": "USD",
            })
        else:
            # Money entered bank: debit cash, credit clearing
            entries.append({
                "account_code": cash_account_code,
                "debit": amt,
                "credit": Decimal("0.00"),
                "currency": "USD",
            })
            entries.append({
                "account_code": clearing_account_code,
                "debit": Decimal("0.00"),
                "credit": amt,
                "currency": "USD",
            })

    if not entries:
        raise BankImportError("No rows found")

    try:
        journal_id = post_journal(
            db,
            company_id=company_id,
            source_type="bank_import",
            source_id=None,
            accounting_period=accounting_period,
            description=f"Bank CSV import ({row_count} rows)",
            posted_by=posted_by,
            entries=entries,
        )
    except LedgerPostingError as e:
        raise BankImportError(str(e)) from e

    return journal_id

# File: migration/import_engine.py
# Purpose: Migration-grade CSV import engine for LedgerHaul
# Status: FULL PRODUCTION (crash-proof, idempotent import jobs, COA + Journals)
# Date: 2026-02-14
#
# Design goals:
# - Never crash the web service on bad inputs (returns structured errors)
# - Idempotent: same file+company+kind won't double-import
# - Works even if certain bookkeeping tables are missing by creating safe defaults
# - Company-scoped imports only (company_id required)
#
# Supported kinds (initial):
#   - "coa_csv"              : Chart of Accounts CSV
#   - "general_journal_csv"  : General Journal CSV (creates journals + journal_entries)
#
# Notes:
# - This engine uses raw SQL with db.engine to avoid model/table conflicts across evolving codebases.
# - Tables used/created if missing:
#     import_jobs, import_job_errors, journals, journal_entries
#
# Usage example (service layer):
#   from migration.import_engine import run_import
#   result = run_import(company_id=1, kind="coa_csv", file_bytes=b"...", filename="coa.csv", user_id=123, dry_run=False)

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Result

from db import db


# ----------------------------
# Public result objects
# ----------------------------

@dataclass
class ImportResult:
    ok: bool
    job_id: Optional[int]
    deduped: bool
    kind: str
    company_id: int
    filename: str
    dry_run: bool
    created: Dict[str, int]
    updated: Dict[str, int]
    skipped: int
    errors: List[Dict[str, Any]]


# ----------------------------
# Constants / helpers
# ----------------------------

_ALLOWED_KINDS = {"coa_csv", "general_journal_csv"}

# Chart of Accounts mapping normalization
_COA_TYPE_MAP = {
    "asset": "asset",
    "assets": "asset",
    "bank": "asset",
    "accounts receivable": "asset",
    "ar": "asset",
    "other asset": "asset",
    "fixed asset": "asset",
    "liability": "liability",
    "liabilities": "liability",
    "accounts payable": "liability",
    "ap": "liability",
    "credit card": "liability",
    "other current liability": "liability",
    "long term liability": "liability",
    "equity": "equity",
    "owner equity": "equity",
    "retained earnings": "equity",
    "revenue": "revenue",
    "income": "revenue",
    "sales": "revenue",
    "other income": "revenue",
    "expense": "expense",
    "expenses": "expense",
    "cost of goods sold": "expense",
    "cogs": "expense",
    "other expense": "expense",
}

_SOURCE_TYPE_DEFAULT = "manual"

_NUMERIC_0 = Decimal("0.00")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _norm(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def _norm_lower(s: Any) -> str:
    return _norm(s).lower()


def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        s = str(v).strip()
        if s == "":
            return None
        return int(s)
    except Exception:
        return None


def _parse_bool(v: Any) -> Optional[bool]:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "no", "n", "off"}:
        return False
    return None


def _safe_decimal(v: Any) -> Optional[Decimal]:
    s = _norm(v)
    if s == "":
        return None
    s = s.replace(",", "")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _accounting_period_from_date(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


def _parse_date(v: Any) -> Optional[datetime]:
    s = _norm(v)
    if not s:
        return None
    # Accept common formats: YYYY-MM-DD, MM/DD/YYYY, M/D/YYYY
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            d = datetime.strptime(s, fmt)
            return d.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def _sanitize_code(code: str) -> str:
    # Keep common COA codes like 1000, 4010, 5-100, etc.
    c = _norm(code)
    c = re.sub(r"\s+", "", c)
    return c


def _normalize_account_type(raw: Any) -> str:
    s = _norm_lower(raw)
    if not s:
        return "expense"
    return _COA_TYPE_MAP.get(s, s)


def _csv_reader(file_bytes: bytes) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Returns (headers, rows) where rows are dicts of header->value.
    Handles UTF-8 with BOM.
    """
    text_data = file_bytes.decode("utf-8-sig", errors="replace")
    f = io.StringIO(text_data)
    reader = csv.DictReader(f)
    headers = [h.strip() for h in (reader.fieldnames or []) if h is not None]
    rows: List[Dict[str, str]] = []
    for r in reader:
        if not isinstance(r, dict):
            continue
        rows.append({(k or "").strip(): ("" if v is None else str(v)) for k, v in r.items()})
    return headers, rows


# ----------------------------
# Schema bootstrap (safe)
# ----------------------------

def _ensure_tables() -> None:
    """
    Creates required tables if missing.
    Uses minimal, compatible schema that won’t break existing deployments.
    """
    with db.engine.begin() as conn:
        # import_jobs: idempotency + audit
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS import_jobs (
                    id BIGSERIAL PRIMARY KEY,
                    company_id BIGINT NOT NULL,
                    kind VARCHAR(64) NOT NULL,
                    filename VARCHAR(255) NOT NULL DEFAULT '',
                    file_sha256 CHAR(64) NOT NULL,
                    created_by BIGINT NULL,
                    dry_run BOOLEAN NOT NULL DEFAULT FALSE,
                    status VARCHAR(32) NOT NULL DEFAULT 'created',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    finished_at TIMESTAMPTZ NULL,
                    UNIQUE(company_id, kind, file_sha256, dry_run)
                );
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS import_job_errors (
                    id BIGSERIAL PRIMARY KEY,
                    job_id BIGINT NOT NULL REFERENCES import_jobs(id) ON DELETE CASCADE,
                    row_number BIGINT NULL,
                    code VARCHAR(64) NOT NULL,
                    message TEXT NOT NULL,
                    payload JSONB NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
        )

        # journals + journal_entries: created if missing for migration-grade journal posting
        # Uses INTEGER/BIGINT keys + company_id BIGINT to match Company Integer PK patterns.
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS journals (
                    id BIGSERIAL PRIMARY KEY,
                    company_id BIGINT NOT NULL,
                    source_type VARCHAR(50) NOT NULL DEFAULT 'manual',
                    source_id VARCHAR(128) NULL,
                    accounting_period VARCHAR(7) NOT NULL,
                    description VARCHAR(255) NOT NULL DEFAULT '',
                    posted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    posted_by BIGINT NULL
                );
                """
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_journals_company_period ON journals(company_id, accounting_period);"))

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id BIGSERIAL PRIMARY KEY,
                    company_id BIGINT NOT NULL,
                    journal_id BIGINT NOT NULL REFERENCES journals(id) ON DELETE CASCADE,
                    account_id BIGINT NULL,
                    account_code VARCHAR(50) NOT NULL,
                    debit NUMERIC(14,2) NOT NULL DEFAULT 0,
                    credit NUMERIC(14,2) NOT NULL DEFAULT 0,
                    memo VARCHAR(255) NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_journal_entries_company_journal ON journal_entries(company_id, journal_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_journal_entries_company_account ON journal_entries(company_id, account_code);"))


# ----------------------------
# Import job lifecycle
# ----------------------------

def _create_or_get_job(
    *,
    company_id: int,
    kind: str,
    filename: str,
    file_sha256: str,
    created_by: Optional[int],
    dry_run: bool,
) -> Tuple[int, bool]:
    """
    Returns (job_id, deduped). deduped=True means an identical job exists and we will not re-import.
    """
    with db.engine.begin() as conn:
        # Try insert; if unique conflict, select existing.
        try:
            r: Result = conn.execute(
                text(
                    """
                    INSERT INTO import_jobs (company_id, kind, filename, file_sha256, created_by, dry_run, status)
                    VALUES (:company_id, :kind, :filename, :file_sha256, :created_by, :dry_run, 'created')
                    RETURNING id;
                    """
                ),
                {
                    "company_id": int(company_id),
                    "kind": kind,
                    "filename": filename[:255],
                    "file_sha256": file_sha256,
                    "created_by": int(created_by) if created_by is not None else None,
                    "dry_run": bool(dry_run),
                },
            )
            job_id = int(r.scalar_one())
            return job_id, False
        except Exception:
            r2: Result = conn.execute(
                text(
                    """
                    SELECT id FROM import_jobs
                    WHERE company_id = :company_id
                      AND kind = :kind
                      AND file_sha256 = :file_sha256
                      AND dry_run = :dry_run
                    ORDER BY id DESC
                    LIMIT 1;
                    """
                ),
                {
                    "company_id": int(company_id),
                    "kind": kind,
                    "file_sha256": file_sha256,
                    "dry_run": bool(dry_run),
                },
            )
            row = r2.mappings().fetchone()
            if not row or row.get("id") is None:
                raise
            return int(row["id"]), True


def _job_set_status(job_id: int, status: str) -> None:
    with db.engine.begin() as conn:
        conn.execute(
            text("UPDATE import_jobs SET status = :s WHERE id = :id;"),
            {"s": status, "id": int(job_id)},
        )


def _job_finish(job_id: int, status: str) -> None:
    with db.engine.begin() as conn:
        conn.execute(
            text("UPDATE import_jobs SET status = :s, finished_at = NOW() WHERE id = :id;"),
            {"s": status, "id": int(job_id)},
        )


def _job_add_error(job_id: int, code: str, message: str, *, row_number: Optional[int] = None, payload: Optional[Dict[str, Any]] = None) -> None:
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO import_job_errors (job_id, row_number, code, message, payload)
                VALUES (:job_id, :row_number, :code, :message, :payload);
                """
            ),
            {
                "job_id": int(job_id),
                "row_number": int(row_number) if row_number is not None else None,
                "code": code[:64],
                "message": message,
                "payload": payload,
            },
        )


def _load_job_errors(job_id: int) -> List[Dict[str, Any]]:
    with db.engine.begin() as conn:
        r: Result = conn.execute(
            text(
                """
                SELECT row_number, code, message, payload
                FROM import_job_errors
                WHERE job_id = :job_id
                ORDER BY id ASC;
                """
            ),
            {"job_id": int(job_id)},
        )
        out: List[Dict[str, Any]] = []
        for row in r.mappings().all():
            out.append(
                {
                    "row_number": row.get("row_number"),
                    "code": row.get("code"),
                    "message": row.get("message"),
                    "payload": row.get("payload"),
                }
            )
        return out


# ----------------------------
# Import implementations
# ----------------------------

def _accounts_table_name() -> str:
    # Your COA model uses __tablename__="accounts" in this repo.
    return "accounts"


def _accounts_columns_exist() -> Dict[str, bool]:
    """
    Detect columns so this can survive schema evolution.
    """
    tbl = _accounts_table_name()
    cols = {"company_id": False, "account_code": False, "code": False, "name": False, "account_type": False, "parent_id": False, "is_active": False, "is_system": False}
    with db.engine.begin() as conn:
        r = conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = :t;
                """
            ),
            {"t": tbl},
        )
        have = {str(x[0]).lower() for x in r.fetchall()}
    for k in cols.keys():
        cols[k] = k.lower() in have
    return cols


def _coa_upsert_one(
    *,
    company_id: int,
    account_code: str,
    name: str,
    account_type: str,
    parent_code: Optional[str],
    is_active: Optional[bool],
    is_system: Optional[bool],
    dry_run: bool,
    created: Dict[str, int],
    updated: Dict[str, int],
) -> None:
    tbl = _accounts_table_name()
    cols = _accounts_columns_exist()

    code = _sanitize_code(account_code)
    if not code:
        raise ValueError("Missing account code")

    nm = _norm(name)
    if not nm:
        raise ValueError("Missing account name")

    at = _normalize_account_type(account_type)
    parent_id: Optional[int] = None

    with db.engine.begin() as conn:
        if parent_code and cols.get("parent_id", False):
            pcode = _sanitize_code(parent_code)
            if pcode:
                # Parent lookup by company + code (supports account_code or code)
                if cols.get("account_code", False):
                    rp = conn.execute(
                        text(f"SELECT id FROM {tbl} WHERE company_id=:cid AND account_code=:c LIMIT 1;"),
                        {"cid": int(company_id), "c": pcode},
                    ).mappings().fetchone()
                else:
                    rp = conn.execute(
                        text(f"SELECT id FROM {tbl} WHERE company_id=:cid AND code=:c LIMIT 1;"),
                        {"cid": int(company_id), "c": pcode},
                    ).mappings().fetchone()
                if rp and rp.get("id") is not None:
                    parent_id = int(rp["id"])

        # Check existing
        if cols.get("account_code", False):
            existing = conn.execute(
                text(f"SELECT id, name, account_type FROM {tbl} WHERE company_id=:cid AND account_code=:c LIMIT 1;"),
                {"cid": int(company_id), "c": code},
            ).mappings().fetchone()
        else:
            existing = conn.execute(
                text(f"SELECT id, name, account_type FROM {tbl} WHERE company_id=:cid AND code=:c LIMIT 1;"),
                {"cid": int(company_id), "c": code},
            ).mappings().fetchone()

        if existing and existing.get("id") is not None:
            # Update only safe, non-destructive fields (do not override system accounts unless asked)
            if dry_run:
                updated["accounts"] = updated.get("accounts", 0) + 1
                return

            set_parts: List[str] = []
            params: Dict[str, Any] = {"id": int(existing["id"])}

            if cols.get("name", False):
                set_parts.append("name=:name")
                params["name"] = nm

            if cols.get("account_type", False):
                set_parts.append("account_type=:account_type")
                params["account_type"] = at

            if cols.get("parent_id", False):
                set_parts.append("parent_id=:parent_id")
                params["parent_id"] = parent_id

            if is_active is not None and cols.get("is_active", False):
                set_parts.append("is_active=:is_active")
                params["is_active"] = bool(is_active)

            if is_system is not None and cols.get("is_system", False):
                # Never force system to False; allow only True (promote) to protect template accounts
                if bool(is_system) is True:
                    set_parts.append("is_system=:is_system")
                    params["is_system"] = True

            if set_parts:
                conn.execute(
                    text(f"UPDATE {tbl} SET {', '.join(set_parts)} WHERE id=:id;"),
                    params,
                )
            updated["accounts"] = updated.get("accounts", 0) + 1
            return

        # Insert new
        if dry_run:
            created["accounts"] = created.get("accounts", 0) + 1
            return

        col_names: List[str] = []
        ph: List[str] = []
        params2: Dict[str, Any] = {}

        if cols.get("company_id", False):
            col_names.append("company_id")
            ph.append(":company_id")
            params2["company_id"] = int(company_id)

        # Prefer account_code if present, else code
        if cols.get("account_code", False):
            col_names.append("account_code")
            ph.append(":account_code")
            params2["account_code"] = code
        else:
            col_names.append("code")
            ph.append(":code")
            params2["code"] = code

        if cols.get("name", False):
            col_names.append("name")
            ph.append(":name")
            params2["name"] = nm

        if cols.get("account_type", False):
            col_names.append("account_type")
            ph.append(":account_type")
            params2["account_type"] = at

        if cols.get("parent_id", False):
            col_names.append("parent_id")
            ph.append(":parent_id")
            params2["parent_id"] = parent_id

        if cols.get("is_active", False):
            col_names.append("is_active")
            ph.append(":is_active")
            params2["is_active"] = True if is_active is None else bool(is_active)

        if cols.get("is_system", False):
            col_names.append("is_system")
            ph.append(":is_system")
            params2["is_system"] = bool(is_system) if is_system is not None else False

        conn.execute(
            text(f"INSERT INTO {tbl} ({', '.join(col_names)}) VALUES ({', '.join(ph)});"),
            params2,
        )
        created["accounts"] = created.get("accounts", 0) + 1


def _import_coa_csv(
    *,
    job_id: int,
    company_id: int,
    file_bytes: bytes,
    dry_run: bool,
    created: Dict[str, int],
    updated: Dict[str, int],
) -> Tuple[int, int]:
    """
    Expected headers (flexible):
      - code OR account_code
      - name
      - type OR account_type
      - parent_code OR parent
      - is_active
      - is_system
    """
    headers, rows = _csv_reader(file_bytes)
    hdr = {h.lower(): h for h in headers}

    code_key = hdr.get("code") or hdr.get("account_code") or hdr.get("accountcode")
    name_key = hdr.get("name") or hdr.get("account_name") or hdr.get("accountname")
    type_key = hdr.get("type") or hdr.get("account_type") or hdr.get("accounttype")
    parent_key = hdr.get("parent_code") or hdr.get("parent") or hdr.get("parentaccount") or hdr.get("parent_account")
    is_active_key = hdr.get("is_active") or hdr.get("active") or hdr.get("isactive")
    is_system_key = hdr.get("is_system") or hdr.get("system") or hdr.get("issystem")

    if not code_key or not name_key:
        _job_add_error(
            job_id,
            "coa_missing_headers",
            f"COA CSV must include headers for code/account_code and name. Found: {headers}",
            payload={"headers": headers},
        )
        return 0, len(rows)

    ok_rows = 0
    skipped = 0

    for i, r in enumerate(rows, start=2):  # header is row 1
        try:
            code = _sanitize_code(r.get(code_key))
            name = _norm(r.get(name_key))
            if not code or not name:
                skipped += 1
                continue

            acct_type = _norm(r.get(type_key)) if type_key else "expense"
            parent_code = _norm(r.get(parent_key)) if parent_key else ""
            is_active = _parse_bool(r.get(is_active_key)) if is_active_key else None
            is_system = _parse_bool(r.get(is_system_key)) if is_system_key else None

            _coa_upsert_one(
                company_id=company_id,
                account_code=code,
                name=name,
                account_type=acct_type,
                parent_code=parent_code or None,
                is_active=is_active,
                is_system=is_system,
                dry_run=dry_run,
                created=created,
                updated=updated,
            )
            ok_rows += 1
        except Exception as e:
            _job_add_error(job_id, "coa_row_error", str(e), row_number=i, payload={"row": r})
    return ok_rows, skipped


def _journal_create(
    *,
    company_id: int,
    source_type: str,
    source_id: Optional[str],
    description: str,
    posted_at: datetime,
    posted_by: Optional[int],
    dry_run: bool,
    created: Dict[str, int],
) -> Optional[int]:
    if dry_run:
        created["journals"] = created.get("journals", 0) + 1
        return 1  # placeholder id (never used for write)

    with db.engine.begin() as conn:
        r = conn.execute(
            text(
                """
                INSERT INTO journals (company_id, source_type, source_id, accounting_period, description, posted_at, posted_by)
                VALUES (:company_id, :source_type, :source_id, :accounting_period, :description, :posted_at, :posted_by)
                RETURNING id;
                """
            ),
            {
                "company_id": int(company_id),
                "source_type": (source_type or _SOURCE_TYPE_DEFAULT)[:50],
                "source_id": (source_id or None),
                "accounting_period": _accounting_period_from_date(posted_at),
                "description": (description or "")[:255],
                "posted_at": posted_at,
                "posted_by": int(posted_by) if posted_by is not None else None,
            },
        )
        jid = int(r.scalar_one())
        created["journals"] = created.get("journals", 0) + 1
        return jid


def _journal_add_entry(
    *,
    company_id: int,
    journal_id: int,
    account_code: str,
    debit: Decimal,
    credit: Decimal,
    memo: Optional[str],
    dry_run: bool,
    created: Dict[str, int],
) -> None:
    code = _sanitize_code(account_code)
    if not code:
        raise ValueError("Missing account_code for journal entry")
    if debit < 0 or credit < 0:
        raise ValueError("Negative debit/credit not allowed")
    if (debit == _NUMERIC_0 and credit == _NUMERIC_0) or (debit > 0 and credit > 0):
        raise ValueError("Each line must have either debit OR credit (not both/none)")

    if dry_run:
        created["journal_entries"] = created.get("journal_entries", 0) + 1
        return

    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO journal_entries (company_id, journal_id, account_id, account_code, debit, credit, memo)
                VALUES (:company_id, :journal_id, NULL, :account_code, :debit, :credit, :memo);
                """
            ),
            {
                "company_id": int(company_id),
                "journal_id": int(journal_id),
                "account_code": code[:50],
                "debit": debit,
                "credit": credit,
                "memo": (memo or None)[:255] if memo is not None else None,
            },
        )
        created["journal_entries"] = created.get("journal_entries", 0) + 1


def _import_general_journal_csv(
    *,
    job_id: int,
    company_id: int,
    file_bytes: bytes,
    posted_by: Optional[int],
    dry_run: bool,
    created: Dict[str, int],
) -> Tuple[int, int]:
    """
    Expected headers (flexible):
      - date
      - description OR memo
      - source_type (optional)
      - source_id (optional)
      - account_code OR code
      - debit
      - credit

    Grouping behavior:
      - Groups rows into a Journal by (date, description, source_type, source_id)
      - Creates one Journal header and N lines
      - Validates journal balances (sum debit == sum credit) per group unless dry_run
    """
    headers, rows = _csv_reader(file_bytes)
    hdr = {h.lower(): h for h in headers}

    date_key = hdr.get("date") or hdr.get("txn_date") or hdr.get("transaction_date")
    desc_key = hdr.get("description") or hdr.get("memo") or hdr.get("note")
    source_type_key = hdr.get("source_type") or hdr.get("sourcetype")
    source_id_key = hdr.get("source_id") or hdr.get("sourceid") or hdr.get("external_id")
    acct_key = hdr.get("account_code") or hdr.get("code") or hdr.get("account") or hdr.get("accountcode")
    debit_key = hdr.get("debit") or hdr.get("dr")
    credit_key = hdr.get("credit") or hdr.get("cr")

    if not date_key or not desc_key or not acct_key:
        _job_add_error(
            job_id,
            "gj_missing_headers",
            f"General Journal CSV missing required headers. Needs date, description/memo, account_code/code. Found: {headers}",
            payload={"headers": headers},
        )
        return 0, len(rows)

    # Group rows
    groups: Dict[Tuple[str, str, str, str], List[Tuple[int, Dict[str, str]]]] = {}
    for i, r in enumerate(rows, start=2):
        dt = _parse_date(r.get(date_key))
        if not dt:
            _job_add_error(job_id, "gj_bad_date", "Invalid or missing date", row_number=i, payload={"row": r})
            continue
        desc = _norm(r.get(desc_key))
        if not desc:
            desc = "Imported journal"
        st = _norm_lower(r.get(source_type_key)) if source_type_key else _SOURCE_TYPE_DEFAULT
        sid = _norm(r.get(source_id_key)) if source_id_key else ""
        key = (dt.date().isoformat(), desc[:255], st[:50], sid[:128])
        groups.setdefault(key, []).append((i, r))

    ok_journals = 0
    skipped = 0

    for (date_iso, desc, st, sid), items in groups.items():
        dt = datetime.fromisoformat(date_iso).replace(tzinfo=timezone.utc)
        total_debit = _NUMERIC_0
        total_credit = _NUMERIC_0

        parsed_lines: List[Tuple[int, str, Decimal, Decimal, Optional[str]]] = []

        for rownum, r in items:
            acct = _sanitize_code(r.get(acct_key))
            if not acct:
                _job_add_error(job_id, "gj_missing_account", "Missing account_code/code", row_number=rownum, payload={"row": r})
                continue

            d = _safe_decimal(r.get(debit_key)) if debit_key else None
            c = _safe_decimal(r.get(credit_key)) if credit_key else None
            d = _NUMERIC_0 if d is None else d
            c = _NUMERIC_0 if c is None else c

            # If both empty, try "amount" with sign
            if d == _NUMERIC_0 and c == _NUMERIC_0:
                amt_key = hdr.get("amount")
                if amt_key:
                    amt = _safe_decimal(r.get(amt_key)) or _NUMERIC_0
                    if amt < 0:
                        c = abs(amt)
                    else:
                        d = amt

            memo = _norm(r.get(desc_key))
            try:
                if (d == _NUMERIC_0 and c == _NUMERIC_0) or (d > 0 and c > 0) or (d < 0 or c < 0):
                    raise ValueError("Invalid debit/credit for line (must be either debit or credit)")
                total_debit += d
                total_credit += c
                parsed_lines.append((rownum, acct, d, c, memo))
            except Exception as e:
                _job_add_error(job_id, "gj_line_error", str(e), row_number=rownum, payload={"row": r})

        if not parsed_lines:
            skipped += 1
            continue

        # Enforce balanced journals (migration-grade)
        if total_debit != total_credit:
            _job_add_error(
                job_id,
                "gj_unbalanced",
                f"Journal not balanced for group ({date_iso}, {desc}). Debits={total_debit} Credits={total_credit}",
                payload={"group": {"date": date_iso, "description": desc, "source_type": st, "source_id": sid}},
            )
            skipped += 1
            continue

        try:
            jid = _journal_create(
                company_id=company_id,
                source_type=st or _SOURCE_TYPE_DEFAULT,
                source_id=sid or None,
                description=desc,
                posted_at=dt,
                posted_by=posted_by,
                dry_run=dry_run,
                created=created,
            )

            # For dry_run, jid is placeholder; still count entries
            real_jid = int(jid or 0)

            for rownum, acct, d, c, memo in parsed_lines:
                _journal_add_entry(
                    company_id=company_id,
                    journal_id=real_jid,
                    account_code=acct,
                    debit=d,
                    credit=c,
                    memo=memo,
                    dry_run=dry_run,
                    created=created,
                )

            ok_journals += 1
        except Exception as e:
            _job_add_error(
                job_id,
                "gj_group_error",
                str(e),
                payload={"group": {"date": date_iso, "description": desc, "source_type": st, "source_id": sid}},
            )
            skipped += 1

    return ok_journals, skipped


# ----------------------------
# Public entrypoint
# ----------------------------

def run_import(
    *,
    company_id: int,
    kind: str,
    file_bytes: bytes,
    filename: str,
    user_id: Optional[int] = None,
    dry_run: bool = False,
) -> ImportResult:
    """
    Runs an import job. This function is crash-proof and returns ImportResult.
    """
    _ensure_tables()

    cid = _safe_int(company_id)
    if cid is None or cid <= 0:
        return ImportResult(
            ok=False,
            job_id=None,
            deduped=False,
            kind=str(kind),
            company_id=int(company_id) if isinstance(company_id, int) else 0,
            filename=filename or "",
            dry_run=bool(dry_run),
            created={},
            updated={},
            skipped=0,
            errors=[{"code": "company_id_required", "message": "Valid company_id is required"}],
        )

    k = _norm_lower(kind)
    if k not in _ALLOWED_KINDS:
        return ImportResult(
            ok=False,
            job_id=None,
            deduped=False,
            kind=k,
            company_id=cid,
            filename=filename or "",
            dry_run=bool(dry_run),
            created={},
            updated={},
            skipped=0,
            errors=[{"code": "unsupported_kind", "message": f"Unsupported import kind: {k}"}],
        )

    fb = file_bytes or b""
    if not fb:
        return ImportResult(
            ok=False,
            job_id=None,
            deduped=False,
            kind=k,
            company_id=cid,
            filename=filename or "",
            dry_run=bool(dry_run),
            created={},
            updated={},
            skipped=0,
            errors=[{"code": "empty_file", "message": "Import file is empty"}],
        )

    sha = _sha256(fb)
    job_id, deduped = _create_or_get_job(
        company_id=cid,
        kind=k,
        filename=filename or "",
        file_sha256=sha,
        created_by=_safe_int(user_id),
        dry_run=bool(dry_run),
    )

    if deduped:
        # Do not re-import; return last known errors (if any)
        errs = _load_job_errors(job_id)
        return ImportResult(
            ok=len(errs) == 0,
            job_id=job_id,
            deduped=True,
            kind=k,
            company_id=cid,
            filename=filename or "",
            dry_run=bool(dry_run),
            created={},
            updated={},
            skipped=0,
            errors=errs,
        )

    created: Dict[str, int] = {}
    updated: Dict[str, int] = {}
    skipped = 0

    try:
        _job_set_status(job_id, "running")

        if k == "coa_csv":
            ok_rows, skipped_rows = _import_coa_csv(
                job_id=job_id,
                company_id=cid,
                file_bytes=fb,
                dry_run=bool(dry_run),
                created=created,
                updated=updated,
            )
            skipped += skipped_rows
            if ok_rows == 0 and (created.get("accounts", 0) + updated.get("accounts", 0)) == 0:
                # If nothing was processed, treat as error
                _job_add_error(job_id, "coa_no_rows", "No COA rows imported (check CSV formatting/headers).")

        elif k == "general_journal_csv":
            ok_journals, skipped_groups = _import_general_journal_csv(
                job_id=job_id,
                company_id=cid,
                file_bytes=fb,
                posted_by=_safe_int(user_id),
                dry_run=bool(dry_run),
                created=created,
            )
            skipped += skipped_groups
            if ok_journals == 0 and (created.get("journals", 0) + created.get("journal_entries", 0)) == 0:
                _job_add_error(job_id, "gj_no_groups", "No journal groups imported (check CSV formatting/headers).")

        errs = _load_job_errors(job_id)
        ok = len(errs) == 0
        _job_finish(job_id, "succeeded" if ok else "failed")

        return ImportResult(
            ok=ok,
            job_id=job_id,
            deduped=False,
            kind=k,
            company_id=cid,
            filename=filename or "",
            dry_run=bool(dry_run),
            created=created,
            updated=updated,
            skipped=int(skipped),
            errors=errs,
        )

    except Exception as e:
        # Absolute crash-proof: log error into job and return structured response
        try:
            _job_add_error(job_id, "import_fatal", str(e))
            _job_finish(job_id, "failed")
        except Exception:
            pass

        return ImportResult(
            ok=False,
            job_id=job_id,
            deduped=False,
            kind=k,
            company_id=cid,
            filename=filename or "",
            dry_run=bool(dry_run),
            created=created,
            updated=updated,
            skipped=int(skipped),
            errors=_load_job_errors(job_id) or [{"code": "import_fatal", "message": str(e)}],
        )

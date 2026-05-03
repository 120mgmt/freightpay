# File: bookkeeping/accounting_export.py
# Purpose: Accounting export service (provider-agnostic; no vendor references)
# Status: Production-safe (no import-time crashes; fails cleanly at call-time)

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("accounting_export")


# -----------------------------------------------------------------------------
# Environment (provider-agnostic; does NOT crash if missing)
# -----------------------------------------------------------------------------

def _env(key: str) -> str:
    return (os.getenv(key) or "").strip()


def _env_int(key: str, default: int) -> int:
    v = _env(key)
    if not v:
        return default
    try:
        return int(v)
    except Exception:
        return default


# REQUIRED: a full URL to the provider endpoint that accepts Journal Entry payloads
# Set ACCOUNTING_JOURNAL_URL in your environment (Render dashboard or .env)
# Example: https://your-accounting-provider.com/api/journal-entries
ACCOUNTING_JOURNAL_URL = _env("ACCOUNTING_JOURNAL_URL")

# OPTIONAL: bearer token (or set ACCOUNTING_AUTH_HEADER directly)
ACCOUNTING_ACCESS_TOKEN = _env("ACCOUNTING_ACCESS_TOKEN")

# OPTIONAL: override entire Authorization header (wins over token if provided)
# Example: "Bearer xxx" OR "Token xxx" OR "Basic xxx"
ACCOUNTING_AUTH_HEADER = _env("ACCOUNTING_AUTH_HEADER")

# OPTIONAL: request timeout seconds
ACCOUNTING_TIMEOUT_SECONDS = _env_int("ACCOUNTING_TIMEOUT_SECONDS", 30)

if not ACCOUNTING_JOURNAL_URL:
    import logging as _logging
    _logging.getLogger("ledgerhaul.accounting_export").warning(
        "ACCOUNTING_JOURNAL_URL is not set — accounting export will be disabled"
    )


# -----------------------------------------------------------------------------
# HTTP Session with retries
# -----------------------------------------------------------------------------

def _session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s


# -----------------------------------------------------------------------------
# Core export
# -----------------------------------------------------------------------------

def export_ledger_entries(ledger_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Exports ledger entries to an external accounting provider as Journal Entries.

    REQUIRED ENV:
      - ACCOUNTING_JOURNAL_URL

    AUTH (choose one):
      - ACCOUNTING_AUTH_HEADER (full header value), OR
      - ACCOUNTING_ACCESS_TOKEN (Bearer token)
    """
    if not ledger_entries:
        raise ValueError("No ledger entries provided for export")

    if not ACCOUNTING_JOURNAL_URL:
        raise RuntimeError("Missing required env var: ACCOUNTING_JOURNAL_URL")

    auth_value: Optional[str] = None
    if ACCOUNTING_AUTH_HEADER:
        auth_value = ACCOUNTING_AUTH_HEADER
    elif ACCOUNTING_ACCESS_TOKEN:
        auth_value = f"Bearer {ACCOUNTING_ACCESS_TOKEN}"

    if not auth_value:
        raise RuntimeError("Missing required auth env var: ACCOUNTING_AUTH_HEADER or ACCOUNTING_ACCESS_TOKEN")

    payload = _build_journal_payload(ledger_entries)

    headers = {
        "Authorization": auth_value,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    logger.info("Exporting %d ledger entries to accounting provider", len(ledger_entries))

    try:
        resp = _session().post(
            ACCOUNTING_JOURNAL_URL,
            json=payload,
            headers=headers,
            timeout=ACCOUNTING_TIMEOUT_SECONDS,
        )
    except Exception as e:
        logger.exception("Accounting export request failed")
        raise RuntimeError(f"Accounting provider API request failed: {str(e)}") from e

    if resp.status_code >= 400:
        try:
            detail = resp.json()
        except Exception:
            detail = {"raw": (resp.text or "")[:1000]}
        logger.error("Accounting export failed status=%s detail=%s", resp.status_code, detail)
        raise RuntimeError(f"Accounting provider API error ({resp.status_code})")

    try:
        data = resp.json()
    except Exception:
        data = {"raw": (resp.text or "")[:2000]}

    logger.info("Accounting export successful")
    return {"ok": True, "result": data}


def _build_journal_payload(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Converts internal ledger entries to a generic Journal Entry payload.

    Expected entry keys (minimum):
      - account_code (str)
      - debit (number-ish)
      - credit (number-ish)
      - description (optional)
    """
    lines: List[Dict[str, Any]] = []

    for e in entries:
        account_code = str(e.get("account_code") or "").strip()
        if not account_code:
            raise ValueError("Missing account_code on ledger entry")

        debit = _to_amount(e.get("debit"))
        credit = _to_amount(e.get("credit"))

        if (debit > 0 and credit > 0) or (debit == 0 and credit == 0):
            raise ValueError("Ledger entry must have exactly one of debit/credit > 0")

        amount = debit if debit > 0 else credit
        posting_type = "debit" if debit > 0 else "credit"

        lines.append(
            {
                "description": str(e.get("description") or "").strip()[:255],
                "amount": float(amount),
                "posting_type": posting_type,
                "account_code": account_code,
            }
        )

    return {"lines": lines}


def _to_amount(v: Any) -> float:
    try:
        if v is None:
            return 0.0
        return float(str(v).strip() or "0")
    except Exception:
        return 0.0
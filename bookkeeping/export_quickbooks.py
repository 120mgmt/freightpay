# freightpay/bookkeeping/export_quickbooks.py

import os
import json
import time
import uuid
import logging
from typing import List, Dict, Any

import requests
from requests.adapters import HTTPAdapter, Retry

# -----------------------------------------------------------------------------
# Logging (production safe)
# -----------------------------------------------------------------------------
logger = logging.getLogger("quickbooks_export")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )
)
logger.addHandler(handler)

# -----------------------------------------------------------------------------
# Environment (required – hard fail if missing)
# -----------------------------------------------------------------------------
QB_CLIENT_ID = os.getenv("QB_CLIENT_ID")
QB_CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
QB_REALM_ID = os.getenv("QB_REALM_ID")
QB_ACCESS_TOKEN = os.getenv("QB_ACCESS_TOKEN")
QB_ENV = os.getenv("QB_ENV", "production").lower()

if not all([QB_CLIENT_ID, QB_CLIENT_SECRET, QB_REALM_ID, QB_ACCESS_TOKEN]):
    raise RuntimeError("Missing required QuickBooks environment variables")

QB_BASE_URL = (
    "https://quickbooks.api.intuit.com"
    if QB_ENV == "production"
    else "https://sandbox-quickbooks.api.intuit.com"
)

# -----------------------------------------------------------------------------
# HTTP Session with retries (idempotent-safe)
# -----------------------------------------------------------------------------
session = requests.Session()
retries = Retry(
    total=5,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"],
)
session.mount("https://", HTTPAdapter(max_retries=retries))

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _headers(idempotency_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {QB_ACCESS_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Request-Id": idempotency_key,
    }


def _post(endpoint: str, payload: Dict[str, Any], idempotency_key: str) -> Dict[str, Any]:
    url = f"{QB_BASE_URL}{endpoint}"
    resp = session.post(url, headers=_headers(idempotency_key), json=payload, timeout=20)

    if resp.status_code not in (200, 201):
        logger.error("QB error %s: %s", resp.status_code, resp.text)
        raise RuntimeError(f"QuickBooks API error {resp.status_code}")

    return resp.json()


# -----------------------------------------------------------------------------
# Core Export Logic
# -----------------------------------------------------------------------------
def export_ledger_entries(
    *,
    company_name: str,
    ledger_entries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Exports ledger entries to QuickBooks as Journal Entries.

    ledger_entries item schema (validated upstream):
    {
        "description": str,
        "amount": float,
        "account_ref": str,
        "posting_type": "Debit" | "Credit"
    }
    """

    if not ledger_entries:
        raise ValueError("No ledger entries provided")

    lines = []
    for entry in ledger_entries:
        if entry["amount"] <= 0:
            raise ValueError("Ledger amount must be positive")

        lines.append(
            {
                "Description": entry["description"],
                "Amount": float(entry["amount"]),
                "DetailType": "JournalEntryLineDetail",
                "JournalEntryLineDetail": {
                    "PostingType": entry["posting_type"],
                    "AccountRef": {"value": entry["account_ref"]},
                },
            }
        )

    payload = {
        "Line": lines,
        "PrivateNote": f"FreightPay export for {company_name}",
    }

    idempotency_key = str(uuid.uuid4())

    logger.info(
        "Exporting %d ledger entries to QuickBooks (realm=%s)",
        len(lines),
        QB_REALM_ID,
    )

    response = _post(
        f"/v3/company/{QB_REALM_ID}/journalentry",
        payload,
        idempotency_key,
    )

    logger.info("QuickBooks export successful: %s", response.get("JournalEntry", {}).get("Id"))
    return response


# -----------------------------------------------------------------------------
# Public API (used by routes / services)
# -----------------------------------------------------------------------------
def export_company_ledger(company_name: str, ledger_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Production entry point.
    Safe to call from routes or background workers.
    """
    start = time.time()
    result = export_ledger_entries(
        company_name=company_name,
        ledger_entries=ledger_entries,
    )
    duration = round(time.time() - start, 2)
    logger.info("QuickBooks export completed in %ss", duration)
    return result

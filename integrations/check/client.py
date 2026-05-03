# File: integrations/check/client.py
# Purpose: Hardened Check API client (sandbox/prod) + webhook signature verification
# Status: Production-ready scaffolding (safe defaults; strict timeouts; retries; idempotency; no provider-specific route coupling)
# Date: 2026-02-22
#
# ENV:
#   CHECK_ENV="sandbox"|"production"        (default: sandbox)
#   CHECK_API_KEY="..."                    (required for API calls)
#   CHECK_API_BASE_URL="https://..."       (optional override; otherwise derived from CHECK_ENV)
#   CHECK_TIMEOUT_SECONDS="45"             (optional)
#   CHECK_USER_AGENT="LedgerHaul/1.0"      (optional)
#   CHECK_WEBHOOK_KEY="..."                (required to verify incoming webhooks)
#
# Check Webhooks:
#   - Signature header: "Check-Signature" (hex/base-16 HMAC-SHA-256 of raw request body using webhook key)
#   - Event id header:  "Check-WebhookEvent-ID" (store to enforce idempotent processing)
#
# References:
#   - API auth style: Authorization: Bearer <API_KEY>
#   - API base URLs: https://sandbox.checkhq.com and https://api.checkhq.com
#   - Webhook signature: Check-Signature (hex) computed via HMAC-SHA-256 over body with webhook key

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import requests


class CheckAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: Optional[int] = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip()
    return v if v else default


def _bool_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def _timeout() -> int:
    try:
        return int(_env("CHECK_TIMEOUT_SECONDS", "45") or "45")
    except Exception:
        return 45


def _base_url() -> str:
    override = _env("CHECK_API_BASE_URL")
    if override:
        return override.rstrip("/")
    env = (_env("CHECK_ENV", "sandbox") or "sandbox").lower()
    if env in {"prod", "production", "live"}:
        return "https://api.checkhq.com"
    return "https://sandbox.checkhq.com"


def _auth_header() -> str:
    api_key = _env("CHECK_API_KEY")
    if not api_key:
        raise CheckAPIError("CHECK_API_KEY is required for Check API calls.")
    return f"Bearer {api_key}"


def _user_agent() -> str:
    return _env("CHECK_USER_AGENT", "LedgerHaul/1.0").strip()


def _sleep_with_jitter(seconds: float) -> None:
    # tiny jitter without importing random (deterministic-ish)
    jitter = (time.time_ns() % 250_000_000) / 1_000_000_000.0  # 0..0.25
    time.sleep(max(0.0, seconds + jitter))


@dataclass(frozen=True)
class CheckClient:
    """
    Thin, hardened client over Check REST endpoints.
    Use this from your provider adapter and/or route handlers.

    Notes:
    - Strict timeouts
    - Safe retry behavior for 429/5xx
    - Optional idempotency key header on state-changing requests
    """

    base_url: str = _base_url()

    def _headers(self, *, idempotency_key: Optional[str] = None) -> Dict[str, str]:
        h = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": _auth_header(),
            "User-Agent": _user_agent(),
        }
        if idempotency_key:
            # Standard header used widely for safe retries; Check docs emphasize idempotency.
            h["Idempotency-Key"] = idempotency_key
        return h

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        retries: int = 3,
    ) -> Tuple[int, Any]:
        url = f"{self.base_url}{path}"
        timeout = _timeout()

        last_err: Optional[Exception] = None
        for attempt in range(0, max(0, retries) + 1):
            try:
                resp = requests.request(
                    method=method.upper(),
                    url=url,
                    headers=self._headers(idempotency_key=idempotency_key),
                    data=json.dumps(body) if body is not None else None,
                    timeout=timeout,
                )

                status = resp.status_code

                # Retry on rate limit / transient server errors
                if status in {429, 500, 502, 503, 504} and attempt < retries:
                    # Respect Retry-After if present
                    ra = resp.headers.get("Retry-After")
                    if ra:
                        try:
                            _sleep_with_jitter(float(ra))
                        except Exception:
                            _sleep_with_jitter(0.8 * (2**attempt))
                    else:
                        _sleep_with_jitter(0.8 * (2**attempt))
                    continue

                # Parse JSON if possible
                try:
                    payload = resp.json()
                except Exception:
                    payload = resp.text

                if 200 <= status < 300:
                    return status, payload

                raise CheckAPIError(
                    f"Check API error {status} for {method.upper()} {path}",
                    status_code=status,
                    payload=payload,
                )

            except Exception as e:
                last_err = e
                # Retry on network/timeout
                if attempt < retries:
                    _sleep_with_jitter(0.6 * (2**attempt))
                    continue
                break

        if isinstance(last_err, CheckAPIError):
            raise last_err
        raise CheckAPIError(f"Check API request failed for {method.upper()} {path}: {last_err}")

    # ------------------------------------------------------------
    # High-value endpoints you’ll use early with Check
    # ------------------------------------------------------------

    def health(self) -> Dict[str, Any]:
        # Not all APIs expose /health; do a lightweight GET that must succeed.
        status, data = self._request("GET", "/forms", retries=1)
        return {"status": "ok", "http": status, "sample": data}

    def create_company(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # POST /companies
        idem = str(uuid.uuid4())
        _, data = self._request("POST", "/companies", body=payload, idempotency_key=idem)
        return data

    def update_company(self, company_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        # PATCH /companies/{id}
        idem = str(uuid.uuid4())
        _, data = self._request("PATCH", f"/companies/{company_id}", body=payload, idempotency_key=idem)
        return data

    def create_employee(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # POST /employees
        idem = str(uuid.uuid4())
        _, data = self._request("POST", "/employees", body=payload, idempotency_key=idem)
        return data

    def create_payroll(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # POST /payrolls
        idem = str(uuid.uuid4())
        _, data = self._request("POST", "/payrolls", body=payload, idempotency_key=idem)
        return data

    def get_payroll(self, payroll_id: str) -> Dict[str, Any]:
        # GET /payrolls/{id}
        _, data = self._request("GET", f"/payrolls/{payroll_id}", retries=2)
        return data

    def create_payroll_item(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # POST /payroll_items
        idem = str(uuid.uuid4())
        _, data = self._request("POST", "/payroll_items", body=payload, idempotency_key=idem)
        return data


# ------------------------------------------------------------
# Webhook signature verification
# ------------------------------------------------------------

def verify_check_webhook_signature(
    *,
    raw_body: bytes,
    signature_header: str,
    webhook_key: Optional[str] = None,
) -> bool:
    """
    Verify Check webhook authenticity.

    Check sends:
      - Check-Signature: hex/base-16 encoded HMAC-SHA-256(raw_body, webhook_key)

    You MUST pass the exact raw request body bytes (no re-serialization).
    """
    key = (webhook_key or _env("CHECK_WEBHOOK_KEY") or "").strip()
    if not key:
        raise CheckAPIError("CHECK_WEBHOOK_KEY is required to verify Check webhooks.")

    sig = (signature_header or "").strip().lower()
    if not sig:
        return False

    mac = hmac.new(key.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256).hexdigest().lower()
    return hmac.compare_digest(mac, sig)


def extract_check_webhook_headers(headers: Dict[str, str]) -> Tuple[str, str]:
    """
    Returns (signature, event_id). Event ID should be stored to enforce idempotency.
    """
    # Flask headers are case-insensitive, but dicts are not; normalize.
    lower = {k.lower(): v for k, v in (headers or {}).items()}
    sig = (lower.get("check-signature") or "").strip()
    event_id = (lower.get("check-webhookevent-id") or lower.get("check-webhookevent-id".lower()) or "").strip()
    # Some stacks may provide "Check-WebhookEvent-ID" exactly; above normalization handles it.
    if not event_id:
        event_id = (lower.get("check-webhookevent-id") or "").strip()
    return sig, event_id

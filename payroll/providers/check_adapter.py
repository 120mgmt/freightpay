# File: payroll/providers/check_adapter.py
# Purpose: Check payroll provider adapter (production-safe, contract-ready scaffolding)
# Status: Hardened + safe defaults (DRY-RUN by default; no writes unless explicitly enabled)
# Date: 2026-02-23
#
# This adapter is designed so you can:
# - Wire ALL Check-facing API plumbing now (client + payload normalization + idempotency + webhook verify)
# - Flip on real writes later after contract signing by setting CHECK_ENABLE_WRITE=true
#
# ENV:
#   CHECK_ENABLE_WRITE="true"|"false"      (default: false)  -> prevents accidental payroll creation pre-contract
#   CHECK_DEFAULT_COMPANY_ID="..."         (optional)        -> fallback company id for provider calls
#
# Uses:
#   integrations.check.client.CheckClient
#   integrations.check.client.verify_check_webhook_signature
#   integrations.check.client.extract_check_webhook_headers

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


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


@dataclass(frozen=True)
class CheckPayrollProvider:
    """
    Adapter surface expected by payroll/provider.py

    Methods:
      - run_payroll(unified_payload) -> creates payroll draft and/or items (DRY-RUN safe by default)
      - fetch_payroll_status(payroll_id) -> reads payroll status
      - verify_webhook(raw_body, headers) -> validates signature + extracts event id
    """

    enable_write: bool = _bool_env("CHECK_ENABLE_WRITE", False)

    def _client(self):
        from integrations.check.client import CheckClient

        return CheckClient()

    # ---------------------------
    # Core operations
    # ---------------------------

    def run_payroll(self, unified_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Contract-ready behavior:
          - If CHECK_ENABLE_WRITE=false (default): returns DRY-RUN description (no outbound calls)
          - If enabled: attempts to create a payroll object and optionally payroll items
        Expected unified_payload patterns (supports multiple shapes safely):
          A) {"company_id": "...", "payroll": {...}, "items": [{...}, ...]}
          B) {"company_id": "...", "provider_payloads": [{...}, ...]}  (mapped worker items)
          C) {"company_id": "...", ...} (passes through to create_payroll)
        """
        company_id = (
            str(unified_payload.get("company_id") or "").strip()
            or (_env("CHECK_DEFAULT_COMPANY_ID") or "").strip()
        )

        payroll_obj = unified_payload.get("payroll")
        items = unified_payload.get("items")

        provider_payloads = unified_payload.get("provider_payloads")
        if isinstance(provider_payloads, list) and not items:
            # Treat mapped payloads as items by default (most common wiring)
            items = provider_payloads

        if not isinstance(items, list):
            items = []

        # DRY-RUN mode prevents accidental writes pre-contract
        if not self.enable_write:
            return {
                "status": "dry_run",
                "provider": "check",
                "enable_write": False,
                "company_id": company_id or None,
                "would_create_payroll": True,
                "would_create_items_count": len(items),
                "note": "Set CHECK_ENABLE_WRITE=true to enable actual Check API writes after contract signing.",
            }

        # Write-enabled mode
        client = self._client()

        # Build safest possible create payload:
        # - If caller provided payroll object, use it
        # - Else, create with remaining top-level keys except items/provider_payloads
        if isinstance(payroll_obj, dict):
            create_payload = dict(payroll_obj)
        else:
            create_payload = {
                k: v
                for k, v in unified_payload.items()
                if k not in {"items", "provider_payloads"}
            }

        # Ensure company id included if present
        if company_id and "company_id" not in create_payload:
            create_payload["company_id"] = company_id

        created = client.create_payroll(create_payload)

        # If Check requires separate item creation, attempt it (safe loop)
        created_items: List[Dict[str, Any]] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            payload = dict(it)

            # Attach payroll reference if we can infer an id
            payroll_id = str(created.get("id") or created.get("payroll_id") or "").strip()
            if payroll_id and "payroll_id" not in payload and "payroll" not in payload:
                payload["payroll_id"] = payroll_id

            try:
                created_items.append(client.create_payroll_item(payload))
            except Exception as e:
                # Do not fail entire run on one bad item; return partials for debugging
                created_items.append({"error": str(e), "input": payload})

        return {
            "status": "created",
            "provider": "check",
            "company_id": company_id or None,
            "payroll": created,
            "items": created_items,
        }

    def fetch_payroll_status(self, payroll_id: str) -> Dict[str, Any]:
        pid = (payroll_id or "").strip()
        if not pid:
            raise ValueError("payroll_id is required")

        client = self._client()
        return client.get_payroll(pid)

    # ---------------------------
    # Webhook support (contract-ready)
    # ---------------------------

    def verify_webhook(self, *, raw_body: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Verifies signature + extracts event_id for idempotency storage.
        Returns:
          {"verified": bool, "event_id": str|None}
        """
        from integrations.check.client import extract_check_webhook_headers, verify_check_webhook_signature

        signature, event_id = extract_check_webhook_headers(headers or {})
        verified = verify_check_webhook_signature(raw_body=raw_body, signature_header=signature)
        return {"verified": bool(verified), "event_id": event_id or None}

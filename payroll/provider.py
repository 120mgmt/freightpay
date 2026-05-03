# File: payroll/provider.py
# Purpose: Provider-agnostic payroll interface (provider-neutral; Check-ready; crash-proof)
# Status: Production-ready (import-safe; never 500s from missing env; safe fallback)
# Date: 2026-02-24

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class PayrollProvider(Protocol):
    """
    Minimal interface the route layer calls.
    Keep provider-specific logic out of routes so swapping providers is controlled.
    """

    name: str

    def build_provider_payload(self, engine_result: Dict[str, Any]) -> Dict[str, Any]:
        """Map internal engine output to provider-specific payload."""
        raise NotImplementedError

    def create_payroll(self, *, company_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a payroll draft/object in the provider."""
        raise NotImplementedError

    def submit_payroll(self, *, company_id: str, payroll_id: str) -> Dict[str, Any]:
        """Submit/finalize the payroll in the provider (or fetch status if submit not enabled)."""
        raise NotImplementedError


@dataclass(frozen=True)
class NoOpProvider:
    """
    Safe fallback provider used when provider is not configured.
    Prevents 500s and allows provider-map route to return deterministic payloads.
    """

    name: str = "none"

    def build_provider_payload(self, engine_result: Dict[str, Any]) -> Dict[str, Any]:
        # Preserve engine output, but mark as non-provider payload.
        out = dict(engine_result or {})
        out["_provider"] = "none"
        out["_note"] = "No active payroll provider configured."
        return out

    def create_payroll(self, *, company_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "noop",
            "provider": "none",
            "company_id": (company_id or "").strip() or None,
            "payload": payload or {},
        }

    def submit_payroll(self, *, company_id: str, payroll_id: str) -> Dict[str, Any]:
        return {
            "status": "noop",
            "provider": "none",
            "company_id": (company_id or "").strip() or None,
            "payroll_id": (payroll_id or "").strip() or None,
        }


@dataclass(frozen=True)
class CheckProvider:
    """
    Provider adapter that delegates to payroll/providers/check_adapter.py
    """

    name: str = "check"

    def build_provider_payload(self, engine_result: Dict[str, Any]) -> Dict[str, Any]:
        # Provider-neutral pass-through for now (no vendor naming leaked).
        # Route layer remains stable; mapper can be introduced later without breaking API.
        out = dict(engine_result or {})
        out["_provider"] = "check"
        return out

    def create_payroll(self, *, company_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Import inside function to keep module import-safe.
        from payroll.providers.check_adapter import CheckPayrollProvider

        provider = CheckPayrollProvider()
        unified: Dict[str, Any] = {"company_id": (company_id or "").strip(), **(payload or {})}
        return provider.run_payroll(unified)

    def submit_payroll(self, *, company_id: str, payroll_id: str) -> Dict[str, Any]:
        # Contract-safe behavior: fetch status (adapter may implement submit later).
        from payroll.providers.check_adapter import CheckPayrollProvider

        provider = CheckPayrollProvider()
        return provider.fetch_payroll_status((payroll_id or "").strip())


def _provider_env() -> str:
    return (os.getenv("PAYROLL_PROVIDER") or "").strip().lower()


def get_payroll_provider(explicit: Optional[str] = None) -> PayrollProvider:
    """
    Provider selector (crash-proof).
    - If PAYROLL_PROVIDER is missing/unknown, returns NoOpProvider (never raises).
    - If provider code is present but import fails, returns NoOpProvider with log.
    """
    provider = (explicit or _provider_env() or "none").strip().lower()

    if provider == "check":
        # Ensure adapter is importable; otherwise, fall back without 500s.
        try:
            from payroll.providers.check_adapter import CheckPayrollProvider  # noqa: F401
            return CheckProvider()
        except Exception as e:
            logger.exception("Check provider selected but adapter import failed: %s", str(e))
            return NoOpProvider()

    if provider in {"none", "noop", "disabled", ""}:
        return NoOpProvider()

    logger.warning("Unsupported PAYROLL_PROVIDER=%r. Using NoOpProvider.", provider)
    return NoOpProvider()

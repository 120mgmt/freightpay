"""
Production Payroll Provider Abstraction Layer

Removes all hard dependencies on any specific payroll vendor.
All external payroll providers (Check, future adapters) must implement
the BasePayrollProvider interface.

HARDENING:
- Never silently "succeed" in production when provider is missing.
- NoOp is allowed only in non-production environments (dev/staging).
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return (v.strip() if v is not None else default).strip()


def _app_env() -> str:
    return (_env("APP_ENV", "production") or "production").lower()


class PayrollProviderError(Exception):
    """Generic payroll provider exception."""
    pass


class BasePayrollProvider(ABC):
    """
    Abstract interface ALL payroll providers must implement.
    Provider-specific logic must remain inside provider adapters.
    """

    @abstractmethod
    def create_company(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def onboard_worker(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def run_payroll(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def fetch_payroll_status(self, payroll_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def terminate_worker(self, worker_id: str) -> Dict[str, Any]:
        raise NotImplementedError


class NoOpPayrollProvider(BasePayrollProvider):
    """
    Non-production only fallback.
    This is a UI-safe stub and MUST NOT be used in production.
    """

    def create_company(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "stub", "provider": "none"}

    def onboard_worker(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "stub", "provider": "none"}

    def run_payroll(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "stub", "provider": "none"}

    def fetch_payroll_status(self, payroll_id: str) -> Dict[str, Any]:
        return {"status": "stub", "provider": "none", "payroll_id": payroll_id}

    def terminate_worker(self, worker_id: str) -> Dict[str, Any]:
        return {"status": "stub", "provider": "none", "worker_id": worker_id}


def get_active_payroll_provider() -> BasePayrollProvider:
    """
    Central factory for selecting active payroll provider.
    Controlled via environment variable: PAYROLL_PROVIDER

    HARDENING:
    - In production: missing/unknown provider is an error (fail closed).
    - In non-production: allow NoOp to keep UI flows testable.
    """

    provider = (_env("PAYROLL_PROVIDER", "") or "").lower()
    env = _app_env()

    if provider == "check":
        from payroll.providers.check_adapter import CheckPayrollProvider

        return CheckPayrollProvider()

    if env in {"dev", "development", "staging", "test"}:
        logger.warning("No active payroll provider configured. Using NoOp provider (env=%s).", env)
        return NoOpPayrollProvider()

    raise PayrollProviderError(
        "No active payroll provider configured for production. "
        "Set PAYROLL_PROVIDER=check (or approved provider) before enabling payroll."
    )

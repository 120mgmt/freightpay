# File: payroll/provider_registry.py
# Purpose: Central payroll provider resolver (no vendor leakage in routes)
# Status: Production-ready
# Date: 2026-02-23

from __future__ import annotations
import os

from payroll.provider_adapter import BasePayrollProvider, PayrollProviderError
from payroll.providers.check_adapter import CheckPayrollProvider


def get_active_payroll_provider() -> BasePayrollProvider:
    """
    Resolves the active payroll provider from environment.
    Prevents silent fallback behavior in production.
    """

    provider = (os.getenv("PAYROLL_PROVIDER") or "").strip().lower()

    if provider == "check":
        return CheckPayrollProvider()

    raise PayrollProviderError(
        "Unsupported or undefined PAYROLL_PROVIDER. Set PAYROLL_PROVIDER=check."
    )

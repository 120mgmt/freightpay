"""
Payroll package initializer

Ensures:
- Provider abstraction is accessible
- No direct vendor imports at module level
- Clean dependency injection pattern
"""

from payroll.provider_adapter import (
    BasePayrollProvider,
    PayrollProviderError,
    get_active_payroll_provider,
)

__all__ = [
    "BasePayrollProvider",
    "PayrollProviderError",
    "get_active_payroll_provider",
]

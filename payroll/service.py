"""
Payroll Service Layer

This module is the ONLY place your application should interact with
the payroll provider abstraction.

No direct vendor calls allowed anywhere else in the codebase.
"""

from __future__ import annotations
from typing import Dict, Any
from payroll import get_active_payroll_provider, PayrollProviderError


class PayrollService:
    """
    Orchestrates payroll actions through the active provider.
    """

    def __init__(self) -> None:
        self.provider = get_active_payroll_provider()

    # ------------------------------------------------------------------
    # Company
    # ------------------------------------------------------------------

    def create_company(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self.provider.create_company(payload)
        except Exception as e:
            raise PayrollProviderError(f"Company creation failed: {str(e)}")

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    def onboard_worker(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self.provider.onboard_worker(payload)
        except Exception as e:
            raise PayrollProviderError(f"Worker onboarding failed: {str(e)}")

    def terminate_worker(self, worker_id: str) -> Dict[str, Any]:
        try:
            return self.provider.terminate_worker(worker_id)
        except Exception as e:
            raise PayrollProviderError(f"Worker termination failed: {str(e)}")

    # ------------------------------------------------------------------
    # Payroll
    # ------------------------------------------------------------------

    def run_payroll(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self.provider.run_payroll(payload)
        except Exception as e:
            raise PayrollProviderError(f"Payroll execution failed: {str(e)}")

    def fetch_payroll_status(self, payroll_id: str) -> Dict[str, Any]:
        try:
            return self.provider.fetch_payroll_status(payroll_id)
        except Exception as e:
            raise PayrollProviderError(f"Payroll status retrieval failed: {str(e)}")

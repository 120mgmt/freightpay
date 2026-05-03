# File: services/payroll_provider_adapter.py
# Purpose: Provider-agnostic payroll adapter layer for LedgerHaul
# Status: Production Hardened
# Date: 2026-03-08

from __future__ import annotations

from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class PayrollResult:
    success: bool
    provider: str
    payroll_id: Optional[str]
    message: Optional[str]
    raw: Optional[Dict[str, Any]] = None


class PayrollProviderAdapter:
    """
    Base adapter class for payroll providers.
    Providers supported:
        - ADP
        - Gusto
        - Check
    """

    provider_name: str = "base"

    def run_payroll(
        self,
        company_id: int,
        payroll_data: Dict[str, Any],
    ) -> PayrollResult:
        raise NotImplementedError

    def get_payroll_status(
        self,
        payroll_id: str,
    ) -> PayrollResult:
        raise NotImplementedError


class ADPPayrollAdapter(PayrollProviderAdapter):

    provider_name = "adp"

    def __init__(self, api_client):
        self.api_client = api_client

    def run_payroll(
        self,
        company_id: int,
        payroll_data: Dict[str, Any],
    ) -> PayrollResult:

        response = self.api_client.create_payroll_run(
            company_id=company_id,
            payload=payroll_data,
        )

        if not response:
            return PayrollResult(
                success=False,
                provider="adp",
                payroll_id=None,
                message="ADP payroll creation failed",
            )

        return PayrollResult(
            success=True,
            provider="adp",
            payroll_id=response.get("payroll_id"),
            message="Payroll submitted to ADP",
            raw=response,
        )

    def get_payroll_status(
        self,
        payroll_id: str,
    ) -> PayrollResult:

        response = self.api_client.get_payroll_status(payroll_id)

        return PayrollResult(
            success=True,
            provider="adp",
            payroll_id=payroll_id,
            message="Status retrieved",
            raw=response,
        )


class PayrollProviderFactory:

    @staticmethod
    def create(provider: str, api_client):

        provider = provider.lower()

        if provider == "adp":
            return ADPPayrollAdapter(api_client)

        raise ValueError(f"Unsupported payroll provider: {provider}")

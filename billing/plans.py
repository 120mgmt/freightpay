# File: billing/plans.py
# Purpose: Load subscription + per-employee Stripe price IDs from env (no hardcoding)
# Date: 2026-01-01
# Status: Production-ready v5 (matches current Render env vars)

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    base_price_id: str
    per_employee_price_id: Optional[str] = None


def _env(key: str) -> str:
    v = os.getenv(key)
    if not v or not v.strip():
        raise RuntimeError(f"Missing required env var: {key}")
    return v.strip()


def load_plans() -> Dict[str, Plan]:
    """
    Production rule:
    - ALL Stripe prices come from env
    - Base subscription price + optional per-employee price
    - Matches Render env exactly
    """

    plans: Dict[str, Plan] = {}

    # Combo: $99 base + $6 / employee
    plans["combo"] = Plan(
        code="combo",
        name="Payroll + Bookkeeping",
        base_price_id=_env("STRIPE_COMBO_PRICE_ID"),
        per_employee_price_id=_env("STRIPE_COMBO_PER_EMPLOYEE_PRICE_ID"),
    )

    # Payroll only: $49 base + $8 / employee
    plans["payroll_only"] = Plan(
        code="payroll_only",
        name="Payroll Only",
        base_price_id=_env("STRIPE_PAYROLL_PRICE_ID"),
        per_employee_price_id=_env("STRIPE_PAYROLL_PER_EMPLOYEE_PRICE_ID"),
    )

    # Bookkeeping only: $69 flat
    plans["bookkeeping_only"] = Plan(
        code="bookkeeping_only",
        name="Bookkeeping Only",
        base_price_id=_env("STRIPE_BOOKKEEPING_PRICE_ID"),
        per_employee_price_id=None,
    )

    return plans

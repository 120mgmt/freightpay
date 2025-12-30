# File: billing/plans.py
# Purpose: Load subscription plans (code/name/Stripe price_id) from env (no hardcoding)

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    price_id: str


def _env_first(*keys: str) -> Optional[str]:
    for k in keys:
        v = os.getenv(k)
        if v is None:
            continue
        v = v.strip()
        if v:
            return v
    return None


def load_plans() -> Dict[str, Plan]:
    """
    Production rule: plans MUST come from env price IDs (no hardcoding).

    Supported env var names (accepts either style):
      - STRIPE_PRICE_ID_STARTER / STRIPE_PRICE_ID_PRO / STRIPE_PRICE_ID_ENTERPRISE
      - STRIPE_PRICE_STARTER / STRIPE_PRICE_GROWTH / STRIPE_PRICE_ENTERPRISE

    Returns:
      Dict[str, Plan] where keys are plan codes. For compatibility, if a PRO price exists
      we also expose "growth" as an alias (and vice-versa).
    """
    starter = _env_first("STRIPE_PRICE_ID_STARTER", "STRIPE_PRICE_STARTER")
    pro = _env_first("STRIPE_PRICE_ID_PRO", "STRIPE_PRICE_GROWTH")
    enterprise = _env_first("STRIPE_PRICE_ID_ENTERPRISE", "STRIPE_PRICE_ENTERPRISE")

    if not starter or not pro:
        raise RuntimeError(
            "Missing required Stripe plan env vars. Provide either:\n"
            "- STRIPE_PRICE_ID_STARTER and STRIPE_PRICE_ID_PRO\n"
            "  (optional: STRIPE_PRICE_ID_ENTERPRISE)\n"
            "OR\n"
            "- STRIPE_PRICE_STARTER and STRIPE_PRICE_GROWTH\n"
            "  (optional: STRIPE_PRICE_ENTERPRISE)"
        )

    plans: Dict[str, Plan] = {}

    # Primary canonical codes used by entitlement mapping
    plans["starter"] = Plan(code="starter", name="Starter", price_id=starter)
    plans["pro"] = Plan(code="pro", name="Pro", price_id=pro)

    # Back-compat alias if any older code expects "growth"
    plans["growth"] = Plan(code="growth", name="Growth", price_id=pro)

    if enterprise:
        plans["enterprise"] = Plan(code="enterprise", name="Enterprise", price_id=enterprise)

    return plans

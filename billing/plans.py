from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    price_id: str


def load_plans() -> Dict[str, Plan]:
    """
    Production rule: plans MUST come from env Price IDs (no hardcoding).
    Required env vars:
      STRIPE_PRICE_STARTER
      STRIPE_PRICE_GROWTH
      STRIPE_PRICE_ENTERPRISE   (optional, but recommended)
    """
    starter = (os.getenv("STRIPE_PRICE_STARTER") or "").strip()
    growth = (os.getenv("STRIPE_PRICE_GROWTH") or "").strip()
    enterprise = (os.getenv("STRIPE_PRICE_ENTERPRISE") or "").strip()

    if not starter or not growth:
        raise RuntimeError("Missing STRIPE_PRICE_STARTER and/or STRIPE_PRICE_GROWTH")

    plans = {
        "starter": Plan(code="starter", name="Starter", price_id=starter),
        "growth": Plan(code="growth", name="Growth", price_id=growth),
    }
    if enterprise:
        plans["enterprise"] = Plan(code="enterprise", name="Enterprise", price_id=enterprise)

    return plans

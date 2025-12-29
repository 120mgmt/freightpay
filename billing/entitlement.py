# billing/entitlement.py

from __future__ import annotations

import os
from typing import Dict, Set, Optional
from flask import request

# =========================
# Environment helpers
# =========================

def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()

def _truthy(val: Optional[str]) -> bool:
    if not val:
        return False
    return val.lower() in {"1", "true", "yes", "y", "on"}

# =========================
# Master switches
# =========================

ENTITLEMENTS_ENABLED = _truthy(_env("ENTITLEMENTS_ENABLED", "1"))
ENTITLEMENTS_BYPASS = _truthy(_env("ENTITLEMENTS_BYPASS", "0"))
DEFAULT_PLAN = _env("CUSTOMER_PLAN_DEFAULT", "free")

# =========================
# Plan → features
# =========================

PLAN_ENTITLEMENTS: Dict[str, Set[str]] = {
    "free": {"dashboard:view"},
    "starter": {"dashboard:view", "billing:portal"},
    "pro": {"dashboard:view", "billing:portal", "payroll:run"},
    "enterprise": {"*"},
}

# =========================
# Stripe price → plan
# =========================

STRIPE_PRICE_TO_PLAN: Dict[str, str] = {
    "price_free": "free",
    "price_starter": "starter",
    "price_pro": "pro",
    "price_enterprise": "enterprise",
}

# =========================
# REQUIRED EXPORT (FIX)
# =========================

def entitlements_from_stripe_price_id(price_id: str) -> Set[str]:
    plan = STRIPE_PRICE_TO_PLAN.get(price_id, DEFAULT_PLAN)
    return PLAN_ENTITLEMENTS.get(plan, set())

# =========================
# Helpers
# =========================

def _get_customer_id() -> Optional[str]:
    cid = request.headers.get("X-Customer-Id")
    if cid:
        return cid
    data = request.get_json(silent=True) or {}
    return data.get("customer_id")

def _get_customer_plan(customer_id: str) -> str:
    return DEFAULT_PLAN

# =========================
# Public check
# =========================

def has_entitlement(feature: str, customer_id: Optional[str] = None) -> bool:
    if not ENTITLEMENTS_ENABLED or ENTITLEMENTS_BYPASS:
        return True

    if not customer_id:
        customer_id = _get_customer_id()

    if not customer_id:
        return False

    plan = _get_customer_plan(customer_id)
    allowed = PLAN_ENTITLEMENTS.get(plan, set())

    return "*" in allowed or feature in allowed

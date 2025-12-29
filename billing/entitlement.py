# billing/entitlement.py
# Centralized entitlement & feature-access control
# Import-safe, production-ready

from __future__ import annotations

import os
from typing import Dict, Set, Iterable, Optional
from flask import request

# -------------------------
# Env helpers
# -------------------------

def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()

def _truthy(val: Optional[str]) -> bool:
    if not val:
        return False
    return val.lower() in {"1", "true", "yes", "y", "on"}

# -------------------------
# Master switches
# -------------------------

ENTITLEMENTS_ENABLED = _truthy(_env("ENTITLEMENTS_ENABLED", "1"))
ENTITLEMENTS_BYPASS = _truthy(_env("ENTITLEMENTS_BYPASS", "0"))

DEFAULT_PLAN = _env("CUSTOMER_PLAN_DEFAULT", "free")

# -------------------------
# Plan → feature map
# -------------------------

PLAN_ENTITLEMENTS: Dict[str, Set[str]] = {
    "free": {
        "dashboard:view",
    },
    "starter": {
        "dashboard:view",
        "billing:portal",
    },
    "pro": {
        "*",
    },
    "enterprise": {
        "*",
    },
}

# -------------------------
# Stripe price → plan map
# -------------------------

STRIPE_PRICE_TO_PLAN: Dict[str, str] = {
    # example:
    # "price_123": "starter",
    # "price_456": "pro",
}

# -------------------------
# Request helpers
# -------------------------

def _get_customer_id() -> Optional[str]:
    cid = request.headers.get("X-Customer-ID")
    if isinstance(cid, str) and cid:
        return cid

    data = request.get_json(silent=True) or {}
    cid = data.get("customer_id")
    if isinstance(cid, str) and cid:
        return cid

    return None

# -------------------------
# Plan resolution
# -------------------------

def _get_customer_plan(customer_id: str) -> str:
    """
    Production hook.
    Replace with DB or Stripe lookup when ready.
    """
    return _env("CUSTOMER_PLAN_DEFAULT", DEFAULT_PLAN)

def entitlements_from_stripe_price_id(price_id: str) -> Set[str]:
    plan = STRIPE_PRICE_TO_PLAN.get(price_id)
    if not plan:
        return set()
    return PLAN_ENTITLEMENTS.get(plan, set())

# -------------------------
# Public API
# -------------------------

def has_entitlement(feature: str, customer_id: Optional[str] = None) -> bool:
    if not ENTITLEMENTS_ENABLED:
        return True

    if ENTITLEMENTS_BYPASS:
        return True

    if not customer_id:
        customer_id = _get_customer_id()

    if not customer_id:
        return False

    plan = _get_customer_plan(customer_id)
    allowed = PLAN_ENTITLEMENTS.get(plan, set())

    if "*" in allowed:
        return True

    return feature in allowed

def entitlements_to_dict(features: Iterable[str]) -> Dict[str, bool]:
    return {f: has_entitlement(f) for f in features}

# -------------------------
# Self-test (safe on import)
# -------------------------

if __name__ == "__main__":
    os.environ["ENTITLEMENTS_ENABLED"] = "1"
    os.environ["ENTITLEMENTS_BYPASS"] = "0"
    os.environ["CUSTOMER_PLAN_DEFAULT"] = "pro"

    assert has_entitlement("dashboard:view", "x") is True
    assert has_entitlement("billing:portal", "x") is True
    assert has_entitlement("admin:users", "x") is True

    print("entitlement.py OK")

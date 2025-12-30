# billing/entitlement.py
# Centralized entitlement & feature-access control
# Import-safe, production-ready

from __future__ import annotations

import os
from typing import Dict, Set, Optional
from flask import request

# ============================================================
# Environment helpers
# ============================================================

def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _truthy(val: Optional[str]) -> bool:
    if not val:
        return False
    return val.lower() in {"1", "true", "yes", "y", "on"}


# ============================================================
# Master switches
# ============================================================

ENTITLEMENTS_ENABLED = _truthy(_env("ENTITLEMENTS_ENABLED", "1"))
ENTITLEMENTS_BYPASS = _truthy(_env("ENTITLEMENTS_BYPASS", "0"))

DEFAULT_PLAN = _env("CUSTOMER_PLAN_DEFAULT", "free")

# ============================================================
# Plan → feature map
# ============================================================

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

# ============================================================
# Stripe price → plan mapping
# ============================================================

STRIPE_PRICE_PLAN_MAP: Dict[str, str] = {
    # example:
    # "price_123": "starter",
}

# ============================================================
# Request helpers
# ============================================================

def _get_customer_id() -> Optional[str]:
    if not request:
        return None

    cid = getattr(request, "customer_id", None)
    if isinstance(cid, str):
        return cid

    data = request.get_json(silent=True) or {}
    cid = data.get("customer_id")
    if isinstance(cid, str):
        return cid

    return None


# ============================================================
# Plan resolution
# ============================================================

def _get_customer_plan(customer_id: str) -> str:
    """
    Production hook.
    Replace with Stripe / DB lookup.
    """
    return _env("CUSTOMER_PLAN_DEFAULT", DEFAULT_PLAN)


def entitlements_from_stripe_price_id(price_id: str) -> Set[str]:
    plan = STRIPE_PRICE_PLAN_MAP.get(price_id, DEFAULT_PLAN)
    return PLAN_ENTITLEMENTS.get(plan, set())


# ============================================================
# Entitlement evaluation
# ============================================================

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


def feature_enabled(feature: str, customer_id: Optional[str] = None) -> bool:
    return has_entitlement(feature, customer_id)


def subscription_required_enabled() -> bool:
    return ENTITLEMENTS_ENABLED and not ENTITLEMENTS_BYPASS


# ============================================================
# Serialization helpers (required by subscription_gate)
# ============================================================

def entitlements_to_dict(plan: Optional[str] = None) -> Dict[str, Set[str]]:
    if plan:
        return {plan: PLAN_ENTITLEMENTS.get(plan, set())}
    return PLAN_ENTITLEMENTS.copy()


# ============================================================
# Minimal self-test (safe on import)
# ============================================================

if __name__ == "__main__":
    os.environ["ENTITLEMENTS_ENABLED"] = "1"
    os.environ["ENTITLEMENTS_BYPASS"] = "0"
    os.environ["CUSTOMER_PLAN_DEFAULT"] = "pro"

    assert has_entitlement("dashboard:view", "x") is True
    assert has_entitlement("billing:portal", "x") is True
    assert has_entitlement("admin:users", "x") is True


    print("entitlement.py OK")

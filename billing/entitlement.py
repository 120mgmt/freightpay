# File: billing/entitlement.py
# Purpose: Centralized entitlement, feature access, and subscription gating
# Import-safe, production-ready

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
# Plan → feature map
# =========================

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

# =========================
# Request helpers
# =========================

def _get_customer_id() -> Optional[str]:
    cid = request.headers.get("X-Customer-Id")
    if isinstance(cid, str):
        return cid

    data = request.get_json(silent=True) or {}
    cid = data.get("customer_id")
    if isinstance(cid, str):
        return cid

    return None


def _get_customer_plan(customer_id: str) -> str:
    # Production hook: replace with Stripe / DB lookup
    return _env("CUSTOMER_PLAN_DEFAULT", DEFAULT_PLAN)


# =========================
# Public API (USED BY subscription_gate.py)
# =========================

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


def entitlements_from_stripe_price_id(price_id: Optional[str]) -> Set[str]:
    if not price_id:
        return set()

    mapping = {
        "price_free": PLAN_ENTITLEMENTS["free"],
        "price_starter": PLAN_ENTITLEMENTS["starter"],
        "price_pro": PLAN_ENTITLEMENTS["pro"],
        "price_enterprise": PLAN_ENTITLEMENTS["enterprise"],
    }

    return mapping.get(price_id, set())


def entitlements_to_dict(plan: Optional[str] = None) -> Dict[str, bool]:
    if not plan:
        plan = DEFAULT_PLAN

    allowed = PLAN_ENTITLEMENTS.get(plan, set())

    if "*" in allowed:
        return {"*": True}

    return {feature: True for feature in allowed}


# =========================
# Minimal self-test
# =========================

if __name__ == "__main__":
    os.environ["ENTITLEMENTS_ENABLED"] = "1"
    os.environ["ENTITLEMENTS_BYPASS"] = "0"
    os.environ["CUSTOMER_PLAN_DEFAULT"] = "pro"

    assert subscription_required_enabled() is True
    assert feature_enabled("dashboard:view", "x") is True
    assert feature_enabled("billing:portal", "x") is True
    assert feature_enabled("admin:users", "x") is True

    print("entitlement.py OK")

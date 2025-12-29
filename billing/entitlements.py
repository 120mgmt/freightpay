# File: billing/entitlement.py
# Language: Python
# Purpose: Centralized entitlement & feature-access control
# Import-safe, production-ready, no side effects on import

from __future__ import annotations

import os
from typing import Dict, Set

from flask import request

# ================================
# Environment helpers
# ================================

def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _truthy(val: str | None) -> bool:
    if not val:
        return False
    return val.lower() in {"1", "true", "yes", "y", "on"}


# ================================
# Entitlement configuration
# ================================

# Master switches
ENTITLEMENTS_ENABLED = _truthy(_env("ENTITLEMENTS_ENABLED", "1"))
ENTITLEMENTS_BYPASS = _truthy(_env("ENTITLEMENTS_BYPASS", "0"))

# Plan → allowed features
PLAN_ENTITLEMENTS: Dict[str, Set[str]] = {
    "free": {
        "dashboard:view",
    },
    "starter": {
        "dashboard:view",
        "payroll:run",
        "payroll:export",
    },
    "pro": {
        "dashboard:view",
        "payroll:run",
        "payroll:export",
        "payroll:history",
        "billing:customers",
        "billing:portal",
    },
    "enterprise": {
        "*",  # full access
    },
}

DEFAULT_PLAN = "free"


# ================================
# Request context helpers
# ================================

def _get_customer_id() -> str | None:
    cid = request.headers.get("X-Customer-Id")
    if cid:
        return cid

    cid = request.args.get("customer_id")
    if cid:
        return cid

    data = request.get_json(silent=True) or {}
    cid = data.get("customer_id")
    if isinstance(cid, str):
        return cid

    return None


def _get_customer_plan(customer_id: str) -> str:
    """
    Production hook.
    Replace with Stripe / DB lookup.

    REQUIRED ENV VAR FOR NOW:
      CUSTOMER_PLAN_DEFAULT=free|starter|pro|enterprise
    """
    return _env("CUSTOMER_PLAN_DEFAULT", DEFAULT_PLAN)


# ================================
# Entitlement evaluation
# ================================

def has_entitlement(feature: str, customer_id: str | None = None) -> bool:
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


# ================================
# Minimal self-test (safe on import)
# ================================

if __name__ == "__main__":
    os.environ["ENTITLEMENTS_ENABLED"] = "1"
    os.environ["ENTITLEMENTS_BYPASS"] = "0"
    os.environ["CUSTOMER_PLAN_DEFAULT"] = "pro"

    assert has_entitlement("dashboard:view", "x") is True
    assert has_entitlement("payroll:run", "x") is True
    assert has_entitlement("billing:portal", "x") is True
    assert has_entitlement("admin:users", "x") is False

    print("entitlement.py OK")

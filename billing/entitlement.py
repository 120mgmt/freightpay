# File: billing/entitlement.py
# Language: Python
# Purpose: Centralized entitlement & feature-access control
# Import-safe, production-ready, no side effects on import

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional, Set

from flask import request

# =============================
# Environment helpers
# =============================


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _truthy(val: Optional[str]) -> bool:
    if not val:
        return False
    return val.lower() in {"1", "true", "yes", "y", "on"}


# =============================
# Master switches
# =============================

# When disabled, everything is allowed (safe default so gating never blocks prod by mistake)
ENTITLEMENTS_ENABLED = _truthy(_env("ENTITLEMENTS_ENABLED", "1"))

# Emergency bypass: when enabled, everything is allowed even if ENTITLEMENTS_ENABLED=1
ENTITLEMENTS_BYPASS = _truthy(_env("ENTITLEMENTS_BYPASS", "0"))

# Default plan when no plan is known (safe: minimal access)
DEFAULT_PLAN = _env("CUSTOMER_PLAN_DEFAULT", "free")

# =============================
# Plan -> feature map
# =============================
# Convention: "*" means all features allowed.
# Add/remove features here as your product grows.

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

# =============================
# Stripe Price ID -> plan map
# =============================
# These env vars should be set to your Stripe recurring Price IDs.
# Example:
#   STRIPE_PRICE_ID_STARTER=price_123
#   STRIPE_PRICE_ID_PRO=price_456
#   STRIPE_PRICE_ID_ENTERPRISE=price_789

PRICE_ID_TO_PLAN: Dict[str, str] = {
    _env("STRIPE_PRICE_ID_STARTER", ""): "starter",
    _env("STRIPE_PRICE_ID_PRO", ""): "pro",
    _env("STRIPE_PRICE_ID_ENTERPRISE", ""): "enterprise",
}

# Remove empty keys to avoid accidental matches on ""
PRICE_ID_TO_PLAN = {k: v for k, v in PRICE_ID_TO_PLAN.items() if k}


# =============================
# Request context helpers
# =============================


def _get_customer_id() -> Optional[str]:
    """
    Best-effort extraction of customer_id from request context.
    - Header: X-Customer-Id
    - Query:  ?customer_id=...
    - JSON:   {"customer_id": "..."}
    """
    try:
        hdr = request.headers.get("X-Customer-Id")
        if isinstance(hdr, str) and hdr.strip():
            return hdr.strip()
    except Exception:
        pass

    try:
        q = request.args.get("customer_id")
        if isinstance(q, str) and q.strip():
            return q.strip()
    except Exception:
        pass

    try:
        data = request.get_json(silent=True) or {}
        cid = data.get("customer_id")
        if isinstance(cid, str) and cid.strip():
            return cid.strip()
    except Exception:
        pass

    return None


# =============================
# Public API (used by subscription_gate / routes)
# =============================


def _get_customer_plan(customer_id: str) -> str:
    """
    Production hook.

    Replace with Stripe/DB lookup when you have persistent customer records.

    For now:
      - CUSTOMER_PLAN_DEFAULT controls the plan used by entitlement checks.
    """
    # Intentionally does NOT call Stripe here to keep imports side-effect free
    # and to avoid network calls during app boot.
    return _env("CUSTOMER_PLAN_DEFAULT", DEFAULT_PLAN)


def entitlements_from_stripe_price_id(price_id: Optional[str]) -> Set[str]:
    """
    Returns the entitlement set implied by a Stripe recurring Price ID.
    Used by subscription_gate when translating Stripe subscription items -> entitlements.
    """
    if not price_id:
        return set()

    plan = PRICE_ID_TO_PLAN.get(price_id, "")
    if not plan:
        # Unknown price id -> no entitlements (safe)
        return set()

    return set(PLAN_ENTITLEMENTS.get(plan, set()))


def entitlements_to_dict(entitlements: Set[str]) -> Dict[str, object]:
    """
    Normalizes entitlement set into a JSON-safe dict.
    """
    return {
        "features": sorted(entitlements),
        "all": ("*" in entitlements),
    }


def has_entitlement(feature: str, customer_id: Optional[str] = None) -> bool:
    """
    Core entitlement check.
    """
    if not ENTITLEMENTS_ENABLED:
        return True

    if ENTITLEMENTS_BYPASS:
        return True

    if not customer_id:
        customer_id = _get_customer_id()

    if not customer_id:
        # No customer context -> deny when entitlements are enabled (secure default)
        return False

    plan = _get_customer_plan(customer_id)
    allowed = PLAN_ENTITLEMENTS.get(plan, set())

    if "*" in allowed:
        return True

    return feature in allowed


def feature_enabled(feature: str, customer_id: Optional[str] = None) -> bool:
    """
    Backward-compatible alias for other modules that expect `feature_enabled`.
    """
    return has_entitlement(feature, customer_id)


# Optional convenience object (safe, lightweight)


@dataclass(frozen=True)
class Entitlements:
    plan: str
    features: Set[str]

    def allows(self, feature: str) -> bool:
        if "*" in self.features:
            return True
        return feature in self.features

    def to_dict(self) -> Dict[str, object]:
        return entitlements_to_dict(self.features)


__all__ = [
    "ENTITLEMENTS_ENABLED",
    "ENTITLEMENTS_BYPASS",
    "PLAN_ENTITLEMENTS",
    "Entitlements",
    "entitlements_from_stripe_price_id",
    "entitlements_to_dict",
    "feature_enabled",
    "has_entitlement",
]

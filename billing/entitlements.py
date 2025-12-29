# File: billing/entitlements.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class Entitlements:
    plan: str
    features: Dict[str, bool]
    limits: Dict[str, int]


# Default feature flags (safe baseline)
DEFAULT_FEATURES: Dict[str, bool] = {
    "payroll": True,
    "payroll_run": True,
    "contractor_pay": True,
    "miles_pay": True,
    "deductions": True,
    "export_csv": True,
    "quickbooks_export": True,
    "stripe_billing": True,
    "customer_portal": True,
    "webhooks": True,
}

DEFAULT_LIMITS: Dict[str, int] = {
    "drivers": 25,
    "payroll_runs_per_month": 8,
    "exports_per_month": 50,
}


# Plan overrides (edit freely)
PLAN_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "free": {
        "features": {**DEFAULT_FEATURES, "payroll_run": False},
        "limits": {**DEFAULT_LIMITS, "drivers": 3, "payroll_runs_per_month": 0, "exports_per_month": 5},
    },
    "starter": {
        "features": {**DEFAULT_FEATURES},
        "limits": {**DEFAULT_LIMITS, "drivers": 10, "payroll_runs_per_month": 2},
    },
    "pro": {
        "features": {**DEFAULT_FEATURES},
        "limits": {**DEFAULT_LIMITS, "drivers": 50, "payroll_runs_per_month": 12, "exports_per_month": 200},
    },
    "enterprise": {
        "features": {**DEFAULT_FEATURES},
        "limits": {**DEFAULT_LIMITS, "drivers": 1000, "payroll_runs_per_month": 1000, "exports_per_month": 10000},
    },
}


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_default_plan() -> str:
    return (os.getenv("DEFAULT_PLAN") or "starter").strip().lower() or "starter"


def _plan_from_env_override() -> Optional[str]:
    p = (os.getenv("PLAN_OVERRIDE") or "").strip().lower()
    return p or None


def _normalize_plan(plan: str) -> str:
    plan = (plan or "").strip().lower()
    if plan in PLAN_DEFINITIONS:
        return plan
    return _get_default_plan()


def entitlements_for_plan(plan: str) -> Entitlements:
    plan = _normalize_plan(plan)
    cfg = PLAN_DEFINITIONS.get(plan, PLAN_DEFINITIONS[_get_default_plan()])
    return Entitlements(plan=plan, features=dict(cfg["features"]), limits=dict(cfg["limits"]))


def entitlements_from_stripe_price_id(price_id: str | None) -> Entitlements:
    """
    Map Stripe Price IDs to plans.
    Set these env vars to match your Stripe Price IDs:
      PRICE_FREE, PRICE_STARTER, PRICE_PRO, PRICE_ENTERPRISE
    """
    override = _plan_from_env_override()
    if override:
        return entitlements_for_plan(override)

    pid = (price_id or "").strip()
    if not pid:
        return entitlements_for_plan(_get_default_plan())

    mapping = {
        (os.getenv("PRICE_FREE") or "").strip(): "free",
        (os.getenv("PRICE_STARTER") or "").strip(): "starter",
        (os.getenv("PRICE_PRO") or "").strip(): "pro",
        (os.getenv("PRICE_ENTERPRISE") or "").strip(): "enterprise",
    }
    plan = mapping.get(pid) or _get_default_plan()
    return entitlements_for_plan(plan)


def merge_entitlements(base: Entitlements, add_features: Optional[Dict[str, bool]] = None, add_limits: Optional[Dict[str, int]] = None) -> Entitlements:
    features = dict(base.features)
    limits = dict(base.limits)
    if add_features:
        features.update({k: bool(v) for k, v in add_features.items()})
    if add_limits:
        limits.update({k: int(v) for k, v in add_limits.items()})
    return Entitlements(plan=base.plan, features=features, limits=limits)


def feature_enabled(ent: Entitlements, feature: str) -> bool:
    return bool(ent.features.get(feature, False))


def limit_value(ent: Entitlements, key: str, default: int = 0) -> int:
    try:
        return int(ent.limits.get(key, default))
    except Exception:
        return default


def entitlements_to_dict(ent: Entitlements) -> Dict[str, Any]:
    return {"plan": ent.plan, "features": dict(ent.features), "limits": dict(ent.limits)}


def subscription_required_enabled() -> bool:
    return _truthy(os.getenv("SUBSCRIPTION_REQUIRED", "0"))

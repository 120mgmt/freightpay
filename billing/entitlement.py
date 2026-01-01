# File: billing/entitlement.py
# Purpose: Define plan entitlements (features + limits) and map Stripe price_id -> entitlements.
# Imports used by subscription_gate.py:
#   from billing.entitlement import (
#       Entitlements, entitlements_from_stripe_price_id, entitlements_to_dict,
#       feature_enabled, subscription_required_enabled
#   )

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class Entitlements:
    """
    Plan entitlements for a customer/subscription.
    - plan: plan name (e.g., "starter", "pro", "enterprise")
    - features: feature flags (e.g., {"payroll_run": True})
    - limits: numeric limits (e.g., {"drivers": 10, "payroll_runs_per_month": 20})
    """
    plan: str
    features: Dict[str, bool] = field(default_factory=dict)
    limits: Dict[str, int] = field(default_factory=dict)


def _truthy(v: Optional[str]) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def subscription_required_enabled() -> bool:
    """
    Master switch for gating:
      SUBSCRIPTION_REQUIRED=1 => enforce subscription gate
      SUBSCRIPTION_REQUIRED=0 => allow all routes without subscription checks
    """
    return _truthy(os.getenv("SUBSCRIPTION_REQUIRED", "0"))


def _i(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return int(default)
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, (int, float)):
            return int(v)
        s = str(v).strip()
        if s == "":
            return int(default)
        return int(float(s))
    except Exception:
        return int(default)


def feature_enabled(ent: Entitlements, feature: str) -> bool:
    """
    Returns True if a feature flag is enabled for this plan.
    Unknown features default to False.
    """
    return bool(ent.features.get(feature, False))


def entitlements_to_dict(ent: Optional[Entitlements]) -> Optional[Dict[str, Any]]:
    if ent is None:
        return None
    return {
        "plan": ent.plan,
        "features": dict(ent.features),
        "limits": dict(ent.limits),
    }


def entitlements_from_dict(d: Optional[Dict[str, Any]]) -> Optional[Entitlements]:
    if not isinstance(d, dict):
        return None
    plan = str(d.get("plan") or "starter")
    features_raw = d.get("features") if isinstance(d.get("features"), dict) else {}
    limits_raw = d.get("limits") if isinstance(d.get("limits"), dict) else {}
    features = {str(k): bool(v) for k, v in features_raw.items()}
    limits = {str(k): _i(v, 0) for k, v in limits_raw.items()}
    return Entitlements(plan=plan, features=features, limits=limits)


# -------------------------
# Default plans (edit safely)
# -------------------------

DEFAULT_PLANS: Dict[str, Entitlements] = {
    "starter": Entitlements(
        plan="starter",
        features={
            "payroll_run": True,
            "payroll_export_csv": True,
            "payroll_finalize": True,
            "billing_checkout": True,
            "billing_portal": True,
            "analytics_basic": True,
            "compliance_basic": True,
        },
        limits={
            "drivers": 10,
            "payroll_runs_per_month": 25,
            "loads_per_month": 250,
            "team_members": 2,
        },
    ),
    "pro": Entitlements(
        plan="pro",
        features={
            "payroll_run": True,
            "payroll_export_csv": True,
            "payroll_finalize": True,
            "billing_checkout": True,
            "billing_portal": True,
            "analytics_basic": True,
            "analytics_advanced": True,
            "compliance_basic": True,
            "compliance_advanced": True,
            "collections": True,
            "integrations_quickbooks": True,
        },
        limits={
            "drivers": 50,
            "payroll_runs_per_month": 200,
            "loads_per_month": 2000,
            "team_members": 10,
        },
    ),
    "enterprise": Entitlements(
        plan="enterprise",
        features={
            "payroll_run": True,
            "payroll_export_csv": True,
            "payroll_finalize": True,
            "billing_checkout": True,
            "billing_portal": True,
            "analytics_basic": True,
            "analytics_advanced": True,
            "compliance_basic": True,
            "compliance_advanced": True,
            "collections": True,
            "integrations_quickbooks": True,
            "integrations_gusto": True,
            "integrations_ach": True,
            "sso": True,
        },
        limits={
            "drivers": 999999,
            "payroll_runs_per_month": 999999,
            "loads_per_month": 999999,
            "team_members": 999999,
        },
    ),
}


def _load_plan_overrides_from_env() -> Dict[str, Entitlements]:
    """
    Optional override via env:
      ENTITLEMENTS_JSON='{"starter":{"features":{"x":true},"limits":{"drivers":15}}, ...}'
    Only merges provided keys; defaults remain for unspecified keys.
    """
    raw = os.getenv("ENTITLEMENTS_JSON")
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return {}
        merged: Dict[str, Entitlements] = {}
        for plan_name, plan_obj in payload.items():
            if not isinstance(plan_obj, dict):
                continue
            base = DEFAULT_PLANS.get(str(plan_name)) or Entitlements(plan=str(plan_name))
            features_in = plan_obj.get("features") if isinstance(plan_obj.get("features"), dict) else {}
            limits_in = plan_obj.get("limits") if isinstance(plan_obj.get("limits"), dict) else {}
            features = dict(base.features)
            limits = dict(base.limits)
            for k, v in features_in.items():
                features[str(k)] = bool(v)
            for k, v in limits_in.items():
                limits[str(k)] = _i(v, limits.get(str(k), 0))
            merged[str(plan_name)] = Entitlements(plan=str(plan_name), features=features, limits=limits)
        return merged
    except Exception:
        return {}


_PLAN_OVERRIDES = _load_plan_overrides_from_env()


def _plan(name: str) -> Entitlements:
    return _PLAN_OVERRIDES.get(name) or DEFAULT_PLANS.get(name) or Entitlements(plan=name)


def _price_map() -> Dict[str, str]:
    """
    Map Stripe price_id -> plan name.

    Supported envs (optional):
      STRIPE_PRICE_ID_STARTER=price_...
      STRIPE_PRICE_ID_PRO=price_...
      STRIPE_PRICE_ID_ENTERPRISE=price_...

    Also supports JSON mapping:
      STRIPE_PRICE_TO_PLAN_JSON='{"price_123":"starter","price_456":"pro"}'
    """
    mapping: Dict[str, str] = {}

    p1 = (os.getenv("STRIPE_PRICE_ID_STARTER") or "").strip()
    p2 = (os.getenv("STRIPE_PRICE_ID_PRO") or "").strip()
    p3 = (os.getenv("STRIPE_PRICE_ID_ENTERPRISE") or "").strip()

    if p1:
        mapping[p1] = "starter"
    if p2:
        mapping[p2] = "pro"
    if p3:
        mapping[p3] = "enterprise"

    raw_json = os.getenv("STRIPE_PRICE_TO_PLAN_JSON")
    if raw_json:
        try:
            j = json.loads(raw_json)
            if isinstance(j, dict):
                for k, v in j.items():
                    if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip():
                        mapping[k.strip()] = v.strip()
        except Exception:
            pass

    return mapping


def entitlements_from_stripe_price_id(price_id: Optional[str]) -> Entitlements:
    """
    Returns plan entitlements for a Stripe subscription's primary price_id.
    If unknown or missing price_id, defaults to "starter" entitlements.
    """
    pid = (price_id or "").strip()
    if not pid:
        return _plan("starter")

    m = _price_map()
    plan_name = m.get(pid) or "starter"
    return _plan(plan_name)


if __name__ == "__main__":
    # Minimal self-checks
    assert subscription_required_enabled() in {True, False}
    e = entitlements_from_stripe_price_id(None)
    assert isinstance(e, Entitlements)
    assert isinstance(e.features, dict)
    assert isinstance(e.limits, dict)
    assert feature_enabled(e, "payroll_run") in {True, False}
    print("billing/entitlement.py OK")







           

   
                
   

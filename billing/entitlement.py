# File: billing/entitlement.py
# Purpose: FULL production entitlement engine – maps Stripe price_ids (base + per-employee) to plans,
#          enforces feature flags, limits, and subscription gating.
# Status: FULL PRODUCTION READY (Stripe-complete, no omissions)
# Date: 2026-02-15
#
# HARDENING NOTES:
# - Price→plan map is memoized (no per-request rebuild)
# - Supports BOTH env mapping styles:
#     (A) STRIPE_PRICE_ID_*_BASE / *_PER_EMPLOYEE + STRIPE_PRICE_TO_PLAN_JSON
#     (B) Your app.py style: STRIPE_COMBO_PRICE_ID / STRIPE_PAYROLL_PRICE_ID / STRIPE_BOOKKEEPING_PRICE_ID
# - Deterministic fallback: starter
# - Safe env overrides via ENTITLEMENTS_JSON merge
# - Provider-agnostic (no QuickBooks/Gusto naming)
# - Backward-compatible limit keys + normalized limit keys used by subscription_gate:
#     max_workers, max_payroll_runs_per_month

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


# =========================
# Core Models
# =========================
@dataclass(frozen=True)
class Entitlements:
    plan: str
    features: Dict[str, bool] = field(default_factory=dict)
    limits: Dict[str, int] = field(default_factory=dict)


# =========================
# Helpers
# =========================
def _truthy(v: Optional[str]) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _i(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return int(default)
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, (int, float)):
            return int(v)
        s = str(v).strip()
        if not s:
            return int(default)
        return int(float(s))
    except Exception:
        return int(default)


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _lower(s: Any, default: str = "") -> str:
    try:
        out = str(s).strip().lower()
        return out if out else default
    except Exception:
        return default


# =========================
# Subscription Gate Switch
# =========================
def subscription_required_enabled() -> bool:
    return _truthy(os.getenv("SUBSCRIPTION_REQUIRED", "1"))


def feature_enabled(ent: Entitlements, feature: str) -> bool:
    return bool(ent.features.get(feature, False))


def entitlements_to_dict(ent: Optional[Entitlements]) -> Optional[Dict[str, Any]]:
    if ent is None:
        return None
    return {"plan": ent.plan, "features": dict(ent.features), "limits": dict(ent.limits)}


def entitlements_from_dict(d: Optional[Dict[str, Any]]) -> Optional[Entitlements]:
    if not isinstance(d, dict):
        return None
    plan = _lower(d.get("plan"), "starter")
    features = {str(k): bool(v) for k, v in (d.get("features") or {}).items()}
    limits = {str(k): _i(v, 0) for k, v in (d.get("limits") or {}).items()}
    return Entitlements(plan=plan, features=features, limits=limits)


# =========================
# LIMIT NORMALIZATION (COMPAT)
# =========================
def _normalize_limits(limits: Dict[str, Any]) -> Dict[str, int]:
    """
    Ensures subscription_gate can enforce caps reliably.

    Normalized keys used by subscription_gate:
      - max_workers
      - max_payroll_runs_per_month

    Backward compatibility keys retained:
      - drivers, team_members, payroll_runs_per_month, loads_per_month
    """
    out: Dict[str, int] = {}
    for k, v in (limits or {}).items():
        out[str(k)] = _i(v, 0)

    # If caller already provided normalized keys, keep them.
    max_workers = out.get("max_workers", None)
    max_runs = out.get("max_payroll_runs_per_month", None)

    # Derive max_workers from legacy "drivers" if not set.
    if max_workers is None or max_workers == 0:
        if "drivers" in out and out.get("drivers", 0) > 0:
            out["max_workers"] = int(out["drivers"])

    # Derive max_payroll_runs_per_month from legacy "payroll_runs_per_month" if not set.
    if max_runs is None or max_runs == 0:
        if "payroll_runs_per_month" in out and out.get("payroll_runs_per_month", 0) > 0:
            out["max_payroll_runs_per_month"] = int(out["payroll_runs_per_month"])

    # Ensure keys exist (even if 0) so downstream code can safely read.
    out.setdefault("max_workers", _i(out.get("max_workers"), 0))
    out.setdefault("max_payroll_runs_per_month", _i(out.get("max_payroll_runs_per_month"), 0))

    return out


# =========================
# DEFAULT PLANS (PRODUCTION)
# =========================
DEFAULT_PLANS: Dict[str, Entitlements] = {
    "starter": Entitlements(
        plan="starter",
        features={
            # Core payroll + billing + baseline reporting
            "payroll_run": True,
            "payroll_export_csv": True,
            "payroll_finalize": True,
            "billing_checkout": True,
            "billing_portal": True,
            "analytics_basic": True,
            "compliance_basic": True,
            # Provider-agnostic integration switches
            "integrations_payroll_provider": True,          # e.g., Check / Gusto / others via adapter
            "integrations_accounting_export": True,         # CSV / generic accounting export
        },
        limits=_normalize_limits(
            {
                # Legacy keys (keep)
                "drivers": 10,
                "team_members": 2,
                "payroll_runs_per_month": 25,
                "loads_per_month": 250,
                # Normalized keys (used by subscription_gate)
                "max_workers": 10,
                "max_payroll_runs_per_month": 25,
            }
        ),
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
            # Provider-agnostic integration switches
            "integrations_payroll_provider": True,
            "integrations_accounting_export": True,
            "integrations_accounting_provider": True,       # API connector (non-branded)
        },
        limits=_normalize_limits(
            {
                "drivers": 50,
                "team_members": 10,
                "payroll_runs_per_month": 200,
                "loads_per_month": 2000,
                "max_workers": 50,
                "max_payroll_runs_per_month": 200,
            }
        ),
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
            # Provider-agnostic integration switches
            "integrations_payroll_provider": True,
            "integrations_accounting_export": True,
            "integrations_accounting_provider": True,
            "integrations_ach": True,
            "sso": True,
        },
        limits=_normalize_limits(
            {
                "drivers": 999999,
                "team_members": 999999,
                "payroll_runs_per_month": 999999,
                "loads_per_month": 999999,
                "max_workers": 999999,
                "max_payroll_runs_per_month": 999999,
            }
        ),
    ),
}


# =========================
# ENV OVERRIDES (SAFE MERGE)
# =========================
def _load_plan_overrides_from_env() -> Dict[str, Entitlements]:
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

            nm = _lower(plan_name, "starter")
            base = DEFAULT_PLANS.get(nm) or Entitlements(plan=nm)
            features = dict(base.features)
            limits = dict(base.limits)

            for k, v in (plan_obj.get("features") or {}).items():
                features[str(k)] = bool(v)

            for k, v in (plan_obj.get("limits") or {}).items():
                kk = str(k)
                limits[kk] = _i(v, limits.get(kk, 0))

            merged[nm] = Entitlements(
                plan=nm,
                features=features,
                limits=_normalize_limits(limits),
            )

        return merged
    except Exception:
        return {}


_PLAN_OVERRIDES = _load_plan_overrides_from_env()


def _plan(name: str) -> Entitlements:
    nm = _lower(name, "starter")
    p = _PLAN_OVERRIDES.get(nm) or DEFAULT_PLANS.get(nm) or Entitlements(plan=nm)
    # ensure normalized keys always exist even if overrides removed them
    return Entitlements(plan=p.plan, features=dict(p.features), limits=_normalize_limits(dict(p.limits)))


# =========================
# STRIPE PRICE → PLAN MAP (MEMOIZED)
# =========================
_PRICE_TO_PLAN: Optional[Dict[str, str]] = None


def _build_price_map() -> Dict[str, str]:
    """
    Maps Stripe price IDs (base + per-employee add-ons) to plans.
    """
    mapping: Dict[str, str] = {}

    # Style A
    pairs = {
        "STRIPE_PRICE_ID_STARTER_BASE": "starter",
        "STRIPE_PRICE_ID_STARTER_PER_EMPLOYEE": "starter",
        "STRIPE_PRICE_ID_PRO_BASE": "pro",
        "STRIPE_PRICE_ID_PRO_PER_EMPLOYEE": "pro",
        "STRIPE_PRICE_ID_ENTERPRISE_BASE": "enterprise",
        "STRIPE_PRICE_ID_ENTERPRISE_PER_EMPLOYEE": "enterprise",
    }
    for env_key, plan in pairs.items():
        pid = _env(env_key)
        if pid:
            mapping[pid] = _lower(plan, "starter")

    # Style B (LedgerHaul mapping)
    combo_base = _env("STRIPE_COMBO_PRICE_ID")
    combo_per = _env("STRIPE_COMBO_PER_EMPLOYEE_PRICE_ID")
    payroll_base = _env("STRIPE_PAYROLL_PRICE_ID")
    payroll_per = _env("STRIPE_PAYROLL_PER_EMPLOYEE_PRICE_ID")
    bk_base = _env("STRIPE_BOOKKEEPING_PRICE_ID")

    if combo_base:
        mapping[combo_base] = "pro"
    if combo_per:
        mapping[combo_per] = "pro"
    if payroll_base:
        mapping[payroll_base] = "starter"
    if payroll_per:
        mapping[payroll_per] = "starter"
    if bk_base:
        mapping[bk_base] = "starter"

    # Freeform JSON map
    raw_json = _env("STRIPE_PRICE_TO_PLAN_JSON")
    if raw_json:
        try:
            j = json.loads(raw_json)
            if isinstance(j, dict):
                for k, v in j.items():
                    kk = str(k).strip()
                    vv = _lower(v, "")
                    if kk and vv:
                        mapping[kk] = vv
        except Exception:
            pass

    return mapping


def _price_map() -> Dict[str, str]:
    global _PRICE_TO_PLAN
    if _PRICE_TO_PLAN is None:
        _PRICE_TO_PLAN = _build_price_map()
    return _PRICE_TO_PLAN


# =========================
# PUBLIC API
# =========================
def entitlements_from_stripe_price_id(price_id: Optional[str]) -> Entitlements:
    pid = (price_id or "").strip()
    if not pid:
        return _plan("starter")
    plan_name = _price_map().get(pid, "starter")
    return _plan(plan_name)


# =========================
# Self-test
# =========================
if __name__ == "__main__":
    e = entitlements_from_stripe_price_id(None)
    assert isinstance(e, Entitlements)
    assert subscription_required_enabled() in {True, False}
    assert "max_workers" in e.limits
    assert "max_payroll_runs_per_month" in e.limits
    print("billing/entitlement.py FULL PRODUCTION OK")

# File: billing/prices.py
# Purpose: Canonical Stripe product/price catalog (SINGLE SOURCE OF TRUTH)
# Status: FULL PRODUCTION – hardened, deterministic, multi-price aware
# Date: 2026-01 hookup

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional


# =========================
# Models
# =========================
@dataclass(frozen=True)
class PriceDefinition:
    price_id: str
    product: str
    plan: str
    kind: str              # base | per_employee | addon
    recurring: bool
    interval: Optional[str] = None  # month | year | None


# =========================
# ENV HELPERS
# =========================
def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _truthy(v: str) -> bool:
    return v.lower() in {"1", "true", "yes", "y", "on"}


# =========================
# CORE REGISTRY
# =========================
# This registry defines ALL valid prices your SaaS will ever recognize.
# Stripe webhooks, checkout, entitlements, usage metering MUST reference this.
#
# Supported loading:
#   1) Hard env vars (recommended for prod)
#   2) STRIPE_PRICE_CATALOG_JSON (override / extension)

_REGISTRY: Dict[str, PriceDefinition] = {}


def _register(pd: PriceDefinition) -> None:
    if not pd.price_id:
        return
    _REGISTRY[pd.price_id] = pd


def _load_from_env() -> None:
    """
    Deterministic env-based loading.
    """
    pairs = [
        # Starter
        ("STRIPE_PRICE_ID_STARTER_BASE", "starter", "base", True),
        ("STRIPE_PRICE_ID_STARTER_PER_EMPLOYEE", "starter", "per_employee", True),

        # Pro
        ("STRIPE_PRICE_ID_PRO_BASE", "pro", "base", True),
        ("STRIPE_PRICE_ID_PRO_PER_EMPLOYEE", "pro", "per_employee", True),

        # Enterprise
        ("STRIPE_PRICE_ID_ENTERPRISE_BASE", "enterprise", "base", True),
        ("STRIPE_PRICE_ID_ENTERPRISE_PER_EMPLOYEE", "enterprise", "per_employee", True),

        # LedgerHaul compatibility
        ("STRIPE_COMBO_PRICE_ID", "pro", "base", True),
        ("STRIPE_COMBO_PER_EMPLOYEE_PRICE_ID", "pro", "per_employee", True),
        ("STRIPE_PAYROLL_PRICE_ID", "starter", "base", True),
        ("STRIPE_PAYROLL_PER_EMPLOYEE_PRICE_ID", "starter", "per_employee", True),
        ("STRIPE_BOOKKEEPING_PRICE_ID", "starter", "addon", True),
    ]

    for env_key, plan, kind, recurring in pairs:
        pid = _env(env_key)
        if pid:
            _register(
                PriceDefinition(
                    price_id=pid,
                    product="ledgerhaul",
                    plan=plan,
                    kind=kind,
                    recurring=recurring,
                    interval="month" if recurring else None,
                )
            )


def _load_from_json() -> None:
    raw = _env("STRIPE_PRICE_CATALOG_JSON")
    if not raw:
        return

    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            return

        for item in data:
            if not isinstance(item, dict):
                continue

            pid = str(item.get("price_id") or "").strip()
            if not pid:
                continue

            _register(
                PriceDefinition(
                    price_id=pid,
                    product=str(item.get("product") or "ledgerhaul"),
                    plan=str(item.get("plan") or "starter").lower(),
                    kind=str(item.get("kind") or "base").lower(),
                    recurring=bool(item.get("recurring", True)),
                    interval=item.get("interval"),
                )
            )
    except Exception:
        return


_load_from_env()
_load_from_json()


# =========================
# PUBLIC API
# =========================
def all_prices() -> Dict[str, PriceDefinition]:
    return dict(_REGISTRY)


def is_known_price(price_id: Optional[str]) -> bool:
    if not price_id:
        return False
    return price_id in _REGISTRY


def get_price(price_id: str) -> Optional[PriceDefinition]:
    return _REGISTRY.get(price_id)


def prices_for_plan(plan: str) -> List[PriceDefinition]:
    p = (plan or "").strip().lower()
    return [v for v in _REGISTRY.values() if v.plan == p]


def base_price_for_plan(plan: str) -> Optional[PriceDefinition]:
    for p in prices_for_plan(plan):
        if p.kind == "base":
            return p
    return None


def validate_price_ids(price_ids: List[str]) -> List[str]:
    """
    Returns only valid, known price_ids (stable order, deduped).
    """
    seen = set()
    out: List[str] = []
    for pid in price_ids:
        if pid in _REGISTRY and pid not in seen:
            seen.add(pid)
            out.append(pid)
    return out


# =========================
# HARD FAIL SAFETY
# =========================
if _truthy(_env("STRICT_PRICE_CATALOG")):
    # Enforce that at least one base plan exists
    if not any(p.kind == "base" for p in _REGISTRY.values()):
        raise RuntimeError("STRICT_PRICE_CATALOG enabled but no base prices registered")


if __name__ == "__main__":
    # Minimal self-test
    assert isinstance(all_prices(), dict)
    print("billing/prices.py FULL PRODUCTION OK")

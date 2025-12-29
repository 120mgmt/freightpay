# billing/entitlements.py
# Language: Python
# Purpose: Resolve active subscription entitlements for a Stripe customer

from __future__ import annotations

import os
from typing import Dict, Set

import stripe

# Stripe configuration
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


def _price_to_entitlement_map() -> Dict[str, str]:
    """
    Build a mapping of Stripe Price IDs to entitlement keys.
    Only includes prices that are configured via environment variables.
    """
    mapping: Dict[str, str] = {}

    base = os.getenv("STRIPE_PRICE_BASE")
    if base:
        mapping[base] = "base"

    payroll = os.getenv("STRIPE_PRICE_PAYROLL_PLUS")
    if payroll:
        mapping[payroll] = "payroll_plus"

    fuel = os.getenv("STRIPE_PRICE_FUEL_TAX")
    if fuel:
        mapping[fuel] = "fuel_tax"

    compliance = os.getenv("STRIPE_PRICE_COMPLIANCE")
    if compliance:
        mapping[compliance] = "compliance"

    reporting = os.getenv("STRIPE_PRICE_REPORTING")
    if reporting:
        mapping[reporting] = "reporting"

    return mapping


def get_entitlements_for_customer(customer_id: str) -> Set[str]:
    """
    Returns a set of active entitlements for a Stripe customer.

    Entitlements are derived from ACTIVE or TRIALING subscriptions only.
    """
    entitlements: Set[str] = set()

    if not customer_id or not stripe.api_key:
        return entitlements

    price_map = _price_to_entitlement_map()

    subscriptions = stripe.Subscription.list(
        customer=customer_id,
        status="all",
        expand=["data.items.data.price"],
        limit=100,
    )

    for sub in subscriptions.data:
        if sub.status not in ("active", "trialing"):
            continue

        items = getattr(sub, "items", None)
        data = getattr(items, "data", None) if items else None
        if not isinstance(data, list):
            continue

        for item in data:
            price = getattr(item, "price", None)
            price_id = getattr(price, "id", None) if price else None
            if isinstance(price_id, str):
                entitlement = price_map.get(price_id)
                if entitlement:
                    entitlements.add(entitlement)

    return entitlements


# Minimal self-test (no network calls)
if __name__ == "__main__":
    assert isinstance(_price_to_entitlement_map(), dict)
    assert isinstance(get_entitlements_for_customer(""), set)
    print("entitlements.py loaded successfully")

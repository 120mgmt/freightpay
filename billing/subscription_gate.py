from __future__ import annotations

import os
from functools import wraps
from typing import Any, Callable, Dict, Optional, Set, TypeVar, cast

import stripe
from flask import jsonify, request

F = TypeVar("F", bound=Callable[..., Any])


def _truthy(value: Optional[str]) -> bool:
    return bool(value) and value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _subscription_required_enabled() -> bool:
    # Default ON in production unless explicitly disabled
    return _truthy(os.getenv("SUBSCRIPTION_REQUIRED", "1"))


def _bypass_enabled() -> bool:
    # Default OFF (only enable temporarily for internal testing)
    return _truthy(os.getenv("SUBSCRIPTION_BYPASS", "0"))


def _extract_customer_id() -> Optional[str]:
    """
    Extract Stripe Customer ID from:
      1) Header: X-Customer-Id
      2) Query:  customer_id
      3) JSON:   customer_id
    """
    cid = request.headers.get("X-Customer-Id")
    if cid and cid.strip():
        return cid.strip()

    cid = request.args.get("customer_id")
    if cid and cid.strip():
        return cid.strip()

    data = request.get_json(silent=True) or {}
    cid = data.get("customer_id")
    if isinstance(cid, str) and cid.strip():
        return cid.strip()

    return None


def _stripe_ready() -> bool:
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        return False
    stripe.api_key = key
    return True


def _active_status(status: Optional[str]) -> bool:
    return status in {"active", "trialing"}


def _price_entitlement_map() -> Dict[str, str]:
    """
    Maps Stripe Price IDs -> entitlement strings.
    Only non-empty env vars are included.
    """
    mapping: Dict[str, str] = {}

    base = os.getenv("STRIPE_PRICE_BASE")
    if base:
        mapping[base] = "base"

    p = os.getenv("STRIPE_PRICE_PAYROLL_PLUS")
    if p:
        mapping[p] = "payroll_plus"

    f = os.getenv("STRIPE_PRICE_FUEL_TAX")
    if f:
        mapping[f] = "fuel_tax"

    c = os.getenv("STRIPE_PRICE_COMPLIANCE")
    if c:
        mapping[c] = "compliance"

    r = os.getenv("STRIPE_PRICE_REPORTING")
    if r:
        mapping[r] = "reporting"

    return mapping


def _get_entitlements(customer_id: str) -> Set[str]:
    """
    Reads entitlements live from Stripe subscription items.
    Returns a set like: {"base","payroll_plus"}.
    """
    if not _stripe_ready():
        return set()

    mapping = _price_entitlement_map()
    entitlements: Set[str] = set()

    subs = stripe.Subscription.list(
        customer=customer_id,
        status="all",
        expand=["data.items.data.price"],
        limit=100,
    )

    for sub in subs.data:
        if not _active_status(getattr(sub, "status", None)):
            continue

        items = getattr(sub, "items", None)
        data = getattr(items, "data", None) if items else None
        if not isinstance(data, list):
            continue

        for it in data:
            price = getattr(it, "price", None)
            price_id = getattr(price, "id", None) if price else None
            if isinstance(price_id, str) and price_id in mapping:
                entitlements.add(mapping[price_id])

    return entitlements


def require_active_subscription(fn: F) -> F:
    """
    Use as: @require_active_subscription   (NO parentheses)
    Enforces:
      - SUBSCRIPTION_REQUIRED=1 (default) + valid customer_id + active subscription (base entitlement)
    """
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not _subscription_required_enabled() or _bypass_enabled():
            return fn(*args, **kwargs)

        customer_id = _extract_customer_id()
        if not customer_id:
            return jsonify({"error": "subscription_required", "message": "Missing customer_id."}), 401

        entitlements = _get_entitlements(customer_id)
        if "base" not in entitlements:
            return jsonify(
                {"error": "subscription_inactive", "message": "Active base subscription required.", "entitlements": sorted(entitlements)}
            ), 402

        return fn(*args, **kwargs)

    return cast(F, wrapper)


def require_entitlement(required: str):
    """
    Use as: @require_entitlement("payroll_plus")
    Enforces base + the specified add-on entitlement.
    """
    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _subscription_required_enabled() or _bypass_enabled():
                return fn(*args, **kwargs)

            customer_id = _extract_customer_id()
            if not customer_id:
                return jsonify({"error": "subscription_required", "message": "Missing customer_id."}), 401

            entitlements = _get_entitlements(customer_id)
            if "base" not in entitlements:
                return jsonify(
                    {"error": "subscription_inactive", "message": "Active base subscription required.", "entitlements": sorted(entitlements)}
                ), 402

            if required not in entitlements:
                return jsonify(
                    {"error": "addon_required", "required": required, "entitlements": sorted(entitlements)}
                ), 402

            return fn(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


if __name__ == "__main__":
    # Minimal self-check (no network calls)
    assert _truthy("1") is True
    assert _truthy("true") is True
    assert _truthy("YES") is True
    assert _truthy("0") is False
    assert _truthy("") is False
    assert _truthy(None) is False
    print("subscription_gate.py self-checks: OK")



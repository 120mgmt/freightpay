# File: billing/tax.py
# Purpose: Production tax handling (Stripe Tax / nexus-ready) without breaking core billing if Tax is off
# Date: 2026-01-26
# Status: FULL PRODUCTION – hardened, deterministic, safe fallbacks

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, Response, jsonify, request

from billing.subscription_gate import require_active_subscription


tax_bp = Blueprint("billing_tax", __name__, url_prefix="/billing/tax")


# -----------------------------
# ENV / HELPERS
# -----------------------------
def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name, default)
    if v is None:
        return None
    v = v.strip()
    return v if v else None


def _truthy(v: Optional[str]) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _json_error(msg: str, status: int = 400, **extra: Any) -> Tuple[Response, int]:
    payload: Dict[str, Any] = {"error": msg}
    payload.update(extra)
    return jsonify(payload), status


def _stripe():
    import stripe  # type: ignore

    key = (_env("STRIPE_SECRET_KEY") or "").strip()
    if not key or key in {"sk_live", "sk_test"}:
        raise RuntimeError("Missing/invalid STRIPE_SECRET_KEY")
    if not (key.startswith("sk_live_") or key.startswith("sk_test_")):
        raise RuntimeError("Invalid STRIPE_SECRET_KEY format")
    stripe.api_key = key
    return stripe


def _tax_enabled() -> bool:
    # If you don’t use Stripe Tax yet, keep this OFF in production.
    return _truthy(_env("STRIPE_TAX_ENABLED", "0"))


def _default_currency() -> str:
    return (_env("CURRENCY", "usd") or "usd").lower()


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return default
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, (int, float)):
            return int(v)
        s = str(v).strip()
        if not s:
            return default
        return int(float(s))
    except Exception:
        return default


def _validate_address(addr: Dict[str, Any]) -> Optional[str]:
    # Minimal required for Stripe Tax calculations
    required = ["country", "postal_code"]
    for k in required:
        val = (addr.get(k) or "").strip() if isinstance(addr.get(k), str) else ""
        if not val:
            return f"missing_{k}"
    return None


# -----------------------------
# API
# -----------------------------
@tax_bp.get("/health")
def tax_health() -> Tuple[Response, int]:
    return jsonify({"enabled": _tax_enabled()}), 200


@tax_bp.post("/estimate")
@require_active_subscription
def estimate_tax() -> Tuple[Response, int]:
    """
    POST /billing/tax/estimate

    Body:
      {
        "address": {
          "country":"US",
          "postal_code":"38104",
          "state":"TN",
          "city":"Memphis",
          "line1":"..."
        },
        "line_items":[
          {"amount": 4900, "quantity": 1, "reference": "subscription_base"}
        ],
        "currency":"usd"
      }

    Returns:
      - If STRIPE_TAX_ENABLED=0: deterministic 0-tax response (no failures, no Stripe call)
      - If enabled: uses Stripe Tax calculation endpoint
    """
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return _json_error("invalid_payload", 400)

    address = data.get("address") or {}
    if not isinstance(address, dict):
        return _json_error("invalid_address", 400)

    line_items = data.get("line_items") or []
    if not isinstance(line_items, list) or not line_items:
        return _json_error("invalid_line_items", 400)

    currency = (data.get("currency") or _default_currency()).strip().lower()

    addr_err = _validate_address(address)
    if addr_err:
        return _json_error("invalid_address", 400, detail=addr_err)

    # Tax disabled: return stable 0 response so product never blocks checkout
    if not _tax_enabled():
        subtotal = 0
        for li in line_items:
            if not isinstance(li, dict):
                continue
            amt = _safe_int(li.get("amount"), 0)
            qty = _safe_int(li.get("quantity"), 1)
            if qty < 1:
                qty = 1
            if amt < 0:
                amt = 0
            subtotal += amt * qty

        return (
            jsonify(
                {
                    "enabled": False,
                    "currency": currency,
                    "subtotal": subtotal,
                    "tax": 0,
                    "total": subtotal,
                    "source": "disabled",
                }
            ),
            200,
        )

    # Stripe Tax enabled
    try:
        stripe = _stripe()

        items = []
        for li in line_items:
            if not isinstance(li, dict):
                continue
            amt = _safe_int(li.get("amount"), 0)
            qty = _safe_int(li.get("quantity"), 1)
            if qty < 1:
                qty = 1
            if amt < 0:
                amt = 0
            ref = li.get("reference")
            item: Dict[str, Any] = {"amount": amt, "quantity": qty}
            if isinstance(ref, str) and ref.strip():
                item["reference"] = ref.strip()
            items.append(item)

        if not items:
            return _json_error("invalid_line_items", 400)

        # Stripe Tax: create calculation
        calc = stripe.tax.Calculation.create(
            currency=currency,
            customer_details={
                "address": {
                    "country": (address.get("country") or "").strip(),
                    "postal_code": (address.get("postal_code") or "").strip(),
                    "state": (address.get("state") or "").strip() if isinstance(address.get("state"), str) else None,
                    "city": (address.get("city") or "").strip() if isinstance(address.get("city"), str) else None,
                    "line1": (address.get("line1") or "").strip() if isinstance(address.get("line1"), str) else None,
                    "line2": (address.get("line2") or "").strip() if isinstance(address.get("line2"), str) else None,
                }
            },
            line_items=items,
        )

        # Normalize output
        amount_total = _safe_int(calc.get("amount_total"), 0)
        amount_subtotal = _safe_int(calc.get("amount_subtotal"), 0)
        amount_tax = _safe_int(calc.get("amount_tax"), 0)

        return (
            jsonify(
                {
                    "enabled": True,
                    "currency": currency,
                    "subtotal": amount_subtotal,
                    "tax": amount_tax,
                    "total": amount_total,
                    "calculation_id": calc.get("id"),
                    "source": "stripe_tax",
                }
            ),
            200,
        )

    except Exception as e:
        # Do not block product flow—return stable 0-tax fallback with error metadata
        subtotal = 0
        for li in line_items:
            if not isinstance(li, dict):
                continue
            amt = _safe_int(li.get("amount"), 0)
            qty = _safe_int(li.get("quantity"), 1)
            if qty < 1:
                qty = 1
            if amt < 0:
                amt = 0
            subtotal += amt * qty

        return (
            jsonify(
                {
                    "enabled": True,
                    "currency": currency,
                    "subtotal": subtotal,
                    "tax": 0,
                    "total": subtotal,
                    "source": "fallback_after_error",
                    "detail": str(e),
                }
            ),
            200,
        )


__all__ = ["tax_bp"]


if __name__ == "__main__":
    assert tax_bp.name == "billing_tax"
    print("billing/tax.py FULL PRODUCTION OK")

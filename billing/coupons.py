# File: billing/coupons.py
# Purpose: Hardened Stripe coupon / promotion-code resolution + safe application to Checkout
# Status: FULL PRODUCTION
# Status: deterministic, abuse-resistant, allowlist-capable, Stripe-safe
# Date: 2026-01-26
#
# Supports:
#  - Promotion Codes (preferred): user enters "SAVE10" -> resolves to Stripe promotion_code id
#  - Coupons (admin/internal): direct coupon id "25OFF" -> resolves to Stripe coupon id (optional)
#  - Allowlist enforcement (recommended for prod): COUPON_ALLOWLIST / PROMO_ALLOWLIST
#  - Optional: require active subscription gating elsewhere
#    (this module only validates discounts)
#
# Env:
#  - STRIPE_SECRET_KEY (required)
#  - DISCOUNTS_ENABLED=1|0 (default 1)
#  - DISCOUNTS_STRICT=1|0 (default 1)
#    -> if strict, invalid codes hard-fail; else ignore safely
#  - PROMO_ALLOWLIST="SAVE10,TRUCKING20" (optional)
#  - COUPON_ALLOWLIST="coupon_123,25OFF"
#    (optional; coupon id or name)
#  - PROMO_MAX_LENGTH=64 (default 64)
#  - PROMO_CACHE_TTL=120 (seconds, default 120)
#
# Usage:
#  from billing.coupons import resolve_discount, apply_discount_to_checkout_params
#  disc = resolve_discount(code="SAVE10")
#  params = apply_discount_to_checkout_params(params, disc)

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


# -----------------------------
# Models
# -----------------------------
@dataclass(frozen=True)
class DiscountResolution:
    ok: bool
    kind: Optional[str] = None
    id: Optional[str] = None
    code: Optional[str] = None
    detail: Optional[str] = None
    coupon_id: Optional[str] = None
    percent_off: Optional[float] = None
    amount_off: Optional[int] = None
    currency: Optional[str] = None
    valid: Optional[bool] = None
    active: Optional[bool] = None


# -----------------------------
# Env helpers
# -----------------------------
def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def _truthy(v: str) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def discounts_enabled() -> bool:
    return _truthy(_env("DISCOUNTS_ENABLED", "1"))


def discounts_strict() -> bool:
    return _truthy(_env("DISCOUNTS_STRICT", "1"))


def _max_length() -> int:
    try:
        return max(8, int(_env("PROMO_MAX_LENGTH", "64")))
    except Exception:
        return 64


def _cache_ttl() -> int:
    try:
        return max(10, int(_env("PROMO_CACHE_TTL", "120")))
    except Exception:
        return 120


def _normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def _allowlist_from_env(name: str) -> Optional[set[str]]:
    raw = _env(name)
    if not raw:
        return None
    items = [x.strip().upper() for x in raw.split(",") if x.strip()]
    return set(items) if items else None


_PROMO_ALLOWLIST = _allowlist_from_env("PROMO_ALLOWLIST")
_COUPON_ALLOWLIST = _allowlist_from_env("COUPON_ALLOWLIST")


def _validate_secret_key(secret: str) -> None:
    if not secret:
        raise RuntimeError("Missing STRIPE_SECRET_KEY env var")
    if secret in {"sk_live", "sk_test"}:
        raise RuntimeError("Invalid STRIPE_SECRET_KEY (truncated)")
    if not (
        secret.startswith("sk_live_")
        or secret.startswith("sk_test_")
    ):
        raise RuntimeError(
            "Invalid STRIPE_SECRET_KEY format "
            "(must start with sk_live_ or sk_test_)"
        )
    if len(secret) < 20:
        raise RuntimeError("Invalid STRIPE_SECRET_KEY (too short)")


def _stripe_import():
    import stripe  # type: ignore

    secret = _env("STRIPE_SECRET_KEY")
    _validate_secret_key(secret)
    stripe.api_key = secret
    return stripe


# -----------------------------
# In-memory cache (best-effort)
# -----------------------------
_CACHE: Dict[str, Tuple[float, DiscountResolution]] = {}


def _cache_get(key: str) -> Optional[DiscountResolution]:
    item = _CACHE.get(key)
    if not item:
        return None
    exp, val = item
    if exp <= time.time():
        _CACHE.pop(key, None)
        return None
    return val


def _cache_set(key: str, val: DiscountResolution) -> None:
    _CACHE[key] = (time.time() + _cache_ttl(), val)


# -----------------------------
# Resolution logic
# -----------------------------
def _allowlist_ok(kind: str, normalized_code_or_id: str) -> bool:
    if kind == "promotion_code":
        if _PROMO_ALLOWLIST is None:
            return True
        return normalized_code_or_id.upper() in _PROMO_ALLOWLIST

    if kind == "coupon":
        if _COUPON_ALLOWLIST is None:
            return True
        return normalized_code_or_id.upper() in _COUPON_ALLOWLIST

    return False


def resolve_discount(*, code: Optional[str]) -> Optional[DiscountResolution]:
    """
    Returns:
      - None if discounts disabled OR empty code
      - DiscountResolution(ok=True, kind=..., id=...) if valid
      - DiscountResolution(ok=False, detail=...) if invalid
        (caller decides strict/ignore)
    """
    if not discounts_enabled():
        return None

    raw = (code or "").strip()
    if not raw:
        return None

    if len(raw) > _max_length():
        return DiscountResolution(
            ok=False,
            code=_normalize_code(raw)[:_max_length()],
            detail="code_too_long",
        )

    norm = _normalize_code(raw)
    cache_key = f"promo::{norm}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    if not _allowlist_ok("promotion_code", norm):
        res = DiscountResolution(
            ok=False,
            kind="promotion_code",
            code=norm,
            detail="promo_not_allowlisted",
        )
        _cache_set(cache_key, res)
        return res

    stripe = _stripe_import()

    try:
        promos = stripe.PromotionCode.list(code=norm, limit=10)
        data = promos.get("data") or []
        chosen = None
        for p in data:
            if bool(p.get("active", False)):
                chosen = p
                break

        if chosen:
            coupon = chosen.get("coupon") or {}
            res = DiscountResolution(
                ok=True,
                kind="promotion_code",
                id=str(chosen.get("id") or ""),
                code=norm,
                coupon_id=str(coupon.get("id") or "") or None,
                percent_off=coupon.get("percent_off"),
                amount_off=coupon.get("amount_off"),
                currency=coupon.get("currency"),
                valid=bool(coupon.get("valid")) if "valid" in coupon else None,
                active=bool(chosen.get("active")) if "active" in chosen else None,
            )
            _cache_set(cache_key, res)
            return res

    except Exception as e:
        res = DiscountResolution(
            ok=False,
            kind="promotion_code",
            code=norm,
            detail=(
                f"stripe_error:{type(e).__name__}"
            ),
        )
        _cache_set(cache_key, res)
        return res

    if not _allowlist_ok("coupon", norm):
        res = DiscountResolution(
            ok=False,
            kind="promotion_code",
            code=norm,
            detail="promo_not_found",
        )
        _cache_set(cache_key, res)
        return res

    coupon_key = f"coupon::{norm}"
    cached2 = _cache_get(coupon_key)
    if cached2:
        _cache_set(cache_key, cached2)
        return cached2

    try:
        c = stripe.Coupon.retrieve(norm)
        if c and bool(c.get("valid", False)):
            res = DiscountResolution(
                ok=True,
                kind="coupon",
                id=str(c.get("id") or ""),
                code=norm,
                coupon_id=str(c.get("id") or "") or None,
                percent_off=c.get("percent_off"),
                amount_off=c.get("amount_off"),
                currency=c.get("currency"),
                valid=bool(c.get("valid")) if "valid" in c else None,
                active=True,
            )
        else:
            res = DiscountResolution(
                ok=False,
                kind="coupon",
                code=norm,
                detail="coupon_invalid",
            )
    except Exception as e:
        res = DiscountResolution(
            ok=False,
            kind="coupon",
            code=norm,
            detail=(
                f"stripe_error:{type(e).__name__}"
            ),
        )

    _cache_set(coupon_key, res)
    _cache_set(cache_key, res)
    return res


# -----------------------------
# Checkout application helpers
# -----------------------------
def apply_discount_to_checkout_params(
    params: Dict[str, Any],
    discount: Optional[DiscountResolution],
) -> Dict[str, Any]:
    """
    Mutates a shallow copy of Stripe Checkout Session create params:
      - uses "discounts": [{"promotion_code": "..."}]
      - or [{"coupon": "..."}]
    """
    out = dict(params or {})

    if discount is None:
        return out

    if not discount.ok or not discount.id or not discount.kind:
        if discounts_strict():
            raise ValueError(discount.detail or "invalid_discount")
        return out

    if discount.kind == "promotion_code":
        out["discounts"] = [{"promotion_code": discount.id}]
        return out

    if discount.kind == "coupon":
        out["discounts"] = [{"coupon": discount.id}]
        return out

    if discounts_strict():
        raise ValueError("invalid_discount_kind")
    return out


def discount_error_payload(
    discount: Optional[DiscountResolution],
) -> Optional[Dict[str, Any]]:
    """
    Safe payload for API responses. Never returns Stripe internals.
    """
    if discount is None:
        return None
    if discount.ok:
        return {
            "ok": True,
            "kind": discount.kind,
            "code": discount.code,
            "coupon_id": discount.coupon_id,
            "percent_off": discount.percent_off,
            "amount_off": discount.amount_off,
            "currency": discount.currency,
        }
    return {
        "ok": False,
        "code": discount.code,
        "detail": discount.detail or "invalid_discount",
    }


__all__ = [
    "DiscountResolution",
    "discounts_enabled",
    "discounts_strict",
    "resolve_discount",
    "apply_discount_to_checkout_params",
    "discount_error_payload",
]


if __name__ == "__main__":
    os.environ["DISCOUNTS_ENABLED"] = "0"
    assert resolve_discount(code="SAVE10") is None

    os.environ["DISCOUNTS_ENABLED"] = "1"
    os.environ["DISCOUNTS_STRICT"] = "0"
    d = resolve_discount(code="")
    assert d is None

    base = {"mode": "subscription"}
    out = apply_discount_to_checkout_params(base, None)
    assert out["mode"] == "subscription"
    print("billing/coupons.py OK")

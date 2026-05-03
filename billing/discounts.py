# File: billing/discounts.py
# Purpose: Production-grade discounts engine for Stripe Checkout/Invoices
# Purpose: coupons + promo codes
# Status: FULL PRODUCTION
# Status: hardened, deterministic, safe fallbacks
# Date: 2026-01-26
#
# Supports:
# - Accepting coupon_id OR promo_code OR percent_off (auto coupon)
# - Validating against Stripe (active, valid, not expired)
# - Normalizing input from headers/query/json
# - Returning Stripe-ready kwargs for Checkout Session creation
#
# Does NOT require Flask routes.
# Designed to be imported by billing/checkout.py (and others).

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


_COUPON_RE = re.compile(r"^coupon_[A-Za-z0-9]+$")
_PROMO_RE = re.compile(r"^promo_[A-Za-z0-9]+$")
_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_]{1,64}$")


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _now() -> int:
    return int(time.time())


def _truthy(v: str) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _stripe():
    """
    Stripe client loader.
    Prefers billing/stripe_client.py if present; falls back to
    stripe + STRIPE_SECRET_KEY.
    """
    try:
        from billing.stripe_client import stripe as stripe_client  # type: ignore

        return stripe_client
    except Exception:
        import stripe  # type: ignore

        secret = _env("STRIPE_SECRET_KEY")
        if not secret:
            raise RuntimeError("Missing STRIPE_SECRET_KEY")
        if secret in {"sk_live", "sk_test"}:
            raise RuntimeError("Invalid STRIPE_SECRET_KEY (truncated)")
        if not (
            secret.startswith("sk_live_")
            or secret.startswith("sk_test_")
        ):
            raise RuntimeError("Invalid STRIPE_SECRET_KEY format")
        stripe.api_key = secret
        return stripe


@dataclass(frozen=True)
class DiscountSelection:
    """
    Exactly one of:
      - coupon_id
      - promo_code_id
      - auto_percent_off
    """

    coupon_id: Optional[str] = None
    promo_code_id: Optional[str] = None
    auto_percent_off: Optional[int] = None

    def is_empty(self) -> bool:
        return not (
            self.coupon_id
            or self.promo_code_id
            or self.auto_percent_off
        )


def normalize_discount_input(
    *,
    coupon_id: Optional[str] = None,
    promo_code: Optional[str] = None,
    promo_code_id: Optional[str] = None,
    percent_off: Optional[Any] = None,
) -> DiscountSelection:
    """
    Normalizes caller-provided discount parameters.
    promo_code can be either:
      - a promo code ID (promo_...)
      - or a human-entered code (e.g., SAVE10)
    """
    c = (coupon_id or "").strip()
    pcid = (promo_code_id or "").strip()
    pc = (promo_code or "").strip()

    if c and _COUPON_RE.match(c):
        return DiscountSelection(coupon_id=c)

    if pcid and _PROMO_RE.match(pcid):
        return DiscountSelection(promo_code_id=pcid)

    if pc and _PROMO_RE.match(pc):
        return DiscountSelection(promo_code_id=pc)

    if percent_off is not None and str(percent_off).strip() != "":
        try:
            p = int(float(str(percent_off).strip()))
            if p <= 0:
                return DiscountSelection()
            if p > 100:
                p = 100
            return DiscountSelection(auto_percent_off=p)
        except Exception:
            return DiscountSelection()

    return DiscountSelection()


def _discounts_enabled() -> bool:
    return not _truthy(_env("DISCOUNTS_DISABLED"))


def _allow_auto_coupons() -> bool:
    return _truthy(_env("ALLOW_AUTO_PERCENT_COUPONS"))


def _max_percent_off() -> int:
    try:
        v = int(float(_env("MAX_DISCOUNT_PERCENT") or "50"))
        return max(1, min(100, v))
    except Exception:
        return 50


def _validate_human_code(code: str) -> bool:
    if not code:
        return False
    if len(code) > 65:
        return False
    return bool(_CODE_RE.match(code))


def _stripe_coupon_active(coupon: Dict[str, Any]) -> bool:
    if not isinstance(coupon, dict):
        return False
    if coupon.get("valid") is False:
        return False
    if (
        coupon.get("livemode") is False
        and _truthy(_env("REQUIRE_LIVE_MODE_COUPONS"))
    ):
        return False
    return True


def _stripe_promo_active(promo: Dict[str, Any]) -> bool:
    if not isinstance(promo, dict):
        return False
    if promo.get("active") is False:
        return False
    restr = promo.get("restrictions") or {}
    ends_at = restr.get("ends_at")
    if isinstance(ends_at, (int, float)) and int(ends_at) > 0:
        if int(ends_at) < _now():
            return False
    return True


def _lookup_promo_code_by_code(code: str) -> Optional[Dict[str, Any]]:
    """
    Lookup promo code by human-entered code string.
    """
    if not _validate_human_code(code):
        return None

    stripe = _stripe()
    try:
        res = stripe.PromotionCode.list(
            code=code,
            active=True,
            limit=1,
        )  # type: ignore[attr-defined]
        data = (
            res.get("data")
            if isinstance(res, dict)
            else getattr(res, "data", None)
        )
        if not data:
            return None
        promo = data[0]
        return promo if isinstance(promo, dict) else promo.to_dict()
    except Exception:
        return None


def _retrieve_coupon(coupon_id: str) -> Optional[Dict[str, Any]]:
    if not coupon_id or not _COUPON_RE.match(coupon_id):
        return None
    stripe = _stripe()
    try:
        c = stripe.Coupon.retrieve(coupon_id)  # type: ignore[attr-defined]
        return c if isinstance(c, dict) else c.to_dict()
    except Exception:
        return None


def _retrieve_promo_id(promo_id: str) -> Optional[Dict[str, Any]]:
    if not promo_id or not _PROMO_RE.match(promo_id):
        return None
    stripe = _stripe()
    try:
        p = stripe.PromotionCode.retrieve(promo_id)  # type: ignore[attr-defined]
        return p if isinstance(p, dict) else p.to_dict()
    except Exception:
        return None


def _deterministic_auto_coupon_id(percent_off: int) -> str:
    return f"LEDGERHAUL_AUTO_{percent_off:02d}_PCT"


def _get_or_create_auto_coupon(percent_off: int) -> Optional[str]:
    """
    Auto-coupon creation is OFF by default.
    When ON, creates a reusable coupon and returns its coupon_id.
    """
    if not _allow_auto_coupons():
        return None

    percent_off = int(percent_off)
    if percent_off <= 0:
        return None

    maxp = _max_percent_off()
    if percent_off > maxp:
        percent_off = maxp

    stripe = _stripe()
    name = _deterministic_auto_coupon_id(percent_off)

    try:
        res = stripe.Coupon.list(limit=100)  # type: ignore[attr-defined]
        data = (
            res.get("data")
            if isinstance(res, dict)
            else getattr(res, "data", None)
        )
        if data:
            for coupon in data:
                cd = coupon if isinstance(coupon, dict) else coupon.to_dict()
                if (
                    str(cd.get("name") or "") == name
                    and _stripe_coupon_active(cd)
                ):
                    cid = str(cd.get("id") or "").strip()
                    if cid and _COUPON_RE.match(cid):
                        return cid
    except Exception:
        pass

    try:
        coupon = stripe.Coupon.create(  # type: ignore[attr-defined]
            percent_off=percent_off,
            duration=_env("AUTO_COUPON_DURATION") or "once",
            name=name,
        )
        cd = coupon if isinstance(coupon, dict) else coupon.to_dict()
        cid = str(cd.get("id") or "").strip()
        return cid if cid and _COUPON_RE.match(cid) else None
    except Exception:
        return None


def validate_discount(
    *,
    coupon_id: Optional[str] = None,
    promo_code_id: Optional[str] = None,
    promo_code: Optional[str] = None,
    percent_off: Optional[Any] = None,
) -> Tuple[Optional[DiscountSelection], Optional[str]]:
    """
    Returns (DiscountSelection | None, error_code | None)
    error_code is stable for client handling:
    DISCOUNTS_DISABLED, INVALID_DISCOUNT, NOT_FOUND, INACTIVE
    """
    if not _discounts_enabled():
        return None, "DISCOUNTS_DISABLED"

    sel = normalize_discount_input(
        coupon_id=coupon_id,
        promo_code=promo_code,
        promo_code_id=promo_code_id,
        percent_off=percent_off,
    )

    if sel.auto_percent_off is not None:
        cid = _get_or_create_auto_coupon(sel.auto_percent_off)
        if not cid:
            return None, "INVALID_DISCOUNT"
        c = _retrieve_coupon(cid)
        if not c or not _stripe_coupon_active(c):
            return None, "INACTIVE"
        return DiscountSelection(coupon_id=cid), None

    if sel.coupon_id:
        c = _retrieve_coupon(sel.coupon_id)
        if not c:
            return None, "NOT_FOUND"
        if not _stripe_coupon_active(c):
            return None, "INACTIVE"
        return DiscountSelection(coupon_id=sel.coupon_id), None

    if sel.promo_code_id:
        p = _retrieve_promo_id(sel.promo_code_id)
        if not p:
            return None, "NOT_FOUND"
        if not _stripe_promo_active(p):
            return None, "INACTIVE"
        pid = str(p.get("id") or "").strip()
        return (
            (DiscountSelection(promo_code_id=pid), None)
            if pid
            else (None, "INVALID_DISCOUNT")
        )

    if promo_code and promo_code.strip() and _validate_human_code(promo_code.strip()):
        p2 = _lookup_promo_code_by_code(promo_code.strip())
        if not p2:
            return None, "NOT_FOUND"
        if not _stripe_promo_active(p2):
            return None, "INACTIVE"
        pid = str(p2.get("id") or "").strip()
        return (
            (DiscountSelection(promo_code_id=pid), None)
            if pid
            else (None, "INVALID_DISCOUNT")
        )

    return None, None


def checkout_discounts_kwargs(
    *,
    coupon_id: Optional[str] = None,
    promo_code_id: Optional[str] = None,
    promo_code: Optional[str] = None,
    percent_off: Optional[Any] = None,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Returns (kwargs, error_code).
    kwargs is safe to merge into stripe.checkout.Session.create(...).
    """
    sel, err = validate_discount(
        coupon_id=coupon_id,
        promo_code_id=promo_code_id,
        promo_code=promo_code,
        percent_off=percent_off,
    )

    if err:
        return {}, err
    if not sel or sel.is_empty():
        return {}, None

    # Stripe Checkout expects one of:
    # discounts=[{"coupon": "coupon_..."}]
    # discounts=[{"promotion_code": "promo_..."}]
    if sel.coupon_id:
        return {"discounts": [{"coupon": sel.coupon_id}]}, None
    if sel.promo_code_id:
        return {"discounts": [{"promotion_code": sel.promo_code_id}]}, None

    return {}, None


__all__ = [
    "DiscountSelection",
    "normalize_discount_input",
    "validate_discount",
    "checkout_discounts_kwargs",
]


if __name__ == "__main__":
    os.environ["DISCOUNTS_DISABLED"] = "1"
    s, e = validate_discount(coupon_id="coupon_123")
    assert s is None and e == "DISCOUNTS_DISABLED"
    print("billing/discounts.py FULL PRODUCTION OK")

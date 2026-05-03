# File: billing/promo_validation.py
# Purpose: Server-side validation for coupons / promotion codes (FULL PRODUCTION)
# Status: Hardened, deterministic, Stripe-safe
# Date: 2026-01-26

from __future__ import annotations

import time
from typing import Dict, Optional

from billing.prices import is_known_price
from billing.plans import is_valid_plan
from billing.stripe_client import stripe_client


class PromoValidationError(Exception):
    pass


def _now() -> int:
    return int(time.time())


def _active(promo: Dict) -> bool:
    return bool(promo.get("active", False))


def _not_expired(promo: Dict) -> bool:
    redeem_by = promo.get("redeem_by")
    return redeem_by is None or int(redeem_by) >= _now()


def _usage_ok(promo: Dict) -> bool:
    max_redemptions = promo.get("max_redemptions")
    times_redeemed = promo.get("times_redeemed", 0)
    if max_redemptions is None:
        return True
    return int(times_redeemed) < int(max_redemptions)


def _plan_allowed(promo: Dict, plan: Optional[str]) -> bool:
    meta = promo.get("metadata") or {}
    allowed = meta.get("plans")
    if not allowed or not plan:
        return True
    allowed_plans = {p.strip().lower() for p in allowed.split(",")}
    return plan.lower() in allowed_plans


def _price_allowed(promo: Dict, price_id: Optional[str]) -> bool:
    meta = promo.get("metadata") or {}
    allowed = meta.get("price_ids")
    if not allowed or not price_id:
        return True
    allowed_prices = {p.strip() for p in allowed.split(",")}
    return price_id in allowed_prices


def validate_promo_code(
    *,
    code: str,
    plan: Optional[str] = None,
    price_id: Optional[str] = None,
) -> Dict:
    """
    Validates a Stripe PromotionCode for server-side enforcement.

    Enforces:
      - active
      - not expired
      - redemption limits
      - plan restrictions (metadata.plans)
      - price restrictions (metadata.price_ids)
    """
    if not code or not isinstance(code, str):
        raise PromoValidationError("invalid_code")

    if plan and not is_valid_plan(plan):
        raise PromoValidationError("invalid_plan")

    if price_id and not is_known_price(price_id):
        raise PromoValidationError("invalid_price")

    promo = stripe_client().PromotionCode.retrieve(code, expand=["coupon"])

    if not _active(promo):
        raise PromoValidationError("promo_inactive")

    if not _not_expired(promo):
        raise PromoValidationError("promo_expired")

    if not _usage_ok(promo):
        raise PromoValidationError("promo_exhausted")

    if not _plan_allowed(promo, plan):
        raise PromoValidationError("promo_not_allowed_for_plan")

    if not _price_allowed(promo, price_id):
        raise PromoValidationError("promo_not_allowed_for_price")

    return {
        "promotion_code_id": promo["id"],
        "coupon_id": promo["coupon"]["id"],
        "percent_off": promo["coupon"].get("percent_off"),
        "amount_off": promo["coupon"].get("amount_off"),
        "currency": promo["coupon"].get("currency"),
        "duration": promo["coupon"].get("duration"),
        "valid": True,
    }


__all__ = ["validate_promo_code", "PromoValidationError"]

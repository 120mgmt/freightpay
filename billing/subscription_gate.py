# File: billing/subscription_gate.py
# Purpose: Production-ready subscription + entitlement gating (MULTI-PRICE compatible)
# Import target: from billing.subscription_gate import require_active_subscription
# Date: 2026-02-24
# Status: Production-grade (DB fast-path + Stripe fallback, company_id support, no retry storms)
#         + HARDENED STATUS HANDLING
#         + PLAN LIMIT ENFORCEMENT (workers + payroll runs/month)
#         + HARDENED FAIL-CLOSED EXCEPTION WRAP (prevents HTML 500)

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, cast
from datetime import datetime, timezone

from flask import jsonify, request
from sqlalchemy import text

from db import db
from billing.customers import get_company_customer, get_or_create_company_customer
from billing.entitlement import (
    Entitlements,
    entitlements_from_stripe_price_id,
    entitlements_to_dict,
    feature_enabled,
    subscription_required_enabled,
)
from billing.entitlement_store import get_customer_subscription

F = TypeVar("F", bound=Callable[..., Any])

# In-memory cache (best-effort; per-process). Stripe fallback only.
# key -> (expires_at_epoch, payload_dict)
_SUB_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _truthy(v: Optional[str]) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _bypass_enabled() -> bool:
    return _truthy(os.getenv("SUBSCRIPTION_BYPASS", "0"))


def _cache_ttl_seconds() -> int:
    try:
        return max(5, int((os.getenv("SUBSCRIPTION_CACHE_TTL", "30") or "30").strip()))
    except Exception:
        return 30


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    now = time.time()
    item = _SUB_CACHE.get(key)
    if not item:
        return None
    expires_at, payload = item
    if expires_at <= now:
        _SUB_CACHE.pop(key, None)
        return None
    return payload


def _cache_set(key: str, payload: Dict[str, Any]) -> None:
    _SUB_CACHE[key] = (time.time() + _cache_ttl_seconds(), payload)


def _extract_company_id() -> Optional[int]:
    # Priority: header -> query -> JSON
    cid = request.headers.get("X-Company-Id")
    if isinstance(cid, str) and cid.strip():
        try:
            v = int(cid.strip())
            return v if v >= 0 else None
        except Exception:
            return None

    cid = request.args.get("company_id")
    if isinstance(cid, str) and cid.strip():
        try:
            v = int(cid.strip())
            return v if v >= 0 else None
        except Exception:
            return None

    data = request.get_json(silent=True) or {}
    if isinstance(data, dict):
        cid2 = data.get("company_id")
        if isinstance(cid2, (str, int)) and str(cid2).strip():
            try:
                v = int(str(cid2).strip())
                return v if v >= 0 else None
            except Exception:
                return None

    return None


def _company_plan_override() -> Optional[str]:
    """companies.plan_override for the requesting company, if any."""
    cid = _extract_company_id()
    if cid is None:
        return None
    try:
        from models.company import Company

        company = db.session.get(Company, cid)
        val = (getattr(company, "plan_override", None) or "").strip().lower()
        return val or None
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return None


def _extract_customer_id() -> Optional[str]:
    cid = request.headers.get("X-Customer-Id")
    if isinstance(cid, str) and cid.strip():
        return cid.strip()

    cid = request.args.get("customer_id")
    if isinstance(cid, str) and cid.strip():
        return cid.strip()

    data = request.get_json(silent=True) or {}
    if isinstance(data, dict):
        cid2 = data.get("customer_id")
        if isinstance(cid2, str) and cid2.strip():
            return cid2.strip()

    return None


def _resolve_stripe_customer_id() -> Optional[str]:
    """
    Production rule:
      - Prefer company_id -> persisted Stripe customer mapping (most stable).
      - Fallback to explicit customer_id if provided.
    """
    company_id = _extract_company_id()
    if company_id is not None:
        rec = get_company_customer(company_id)
        if rec and isinstance(rec.get("stripe_customer_id"), str) and rec["stripe_customer_id"].startswith("cus_"):
            return rec["stripe_customer_id"]

        # If company exists but mapping missing, recover/create (keeps things production-stable)
        rec2 = get_or_create_company_customer(company_id=company_id)
        scid = (rec2.get("stripe_customer_id") or "").strip()
        return scid if scid.startswith("cus_") else None

    # Fallback: allow direct customer_id (legacy)
    return _extract_customer_id()


def _stripe_secret_key() -> str:
    return (os.getenv("STRIPE_SECRET_KEY") or "").strip()


def _stripe_enabled() -> bool:
    return bool(_stripe_secret_key())


def _validate_stripe_secret_key(secret: str) -> None:
    if not secret:
        raise RuntimeError("Missing STRIPE_SECRET_KEY env var")
    if secret in {"sk_live", "sk_test"}:
        raise RuntimeError("Invalid STRIPE_SECRET_KEY (truncated)")
    if not (secret.startswith("sk_live_") or secret.startswith("sk_test_")):
        raise RuntimeError("Invalid STRIPE_SECRET_KEY format (must start with sk_live_ or sk_test_)")
    if len(secret) < 20:
        raise RuntimeError("Invalid STRIPE_SECRET_KEY (too short)")


def _stripe_import():
    import stripe  # type: ignore

    secret = _stripe_secret_key()
    _validate_stripe_secret_key(secret)
    stripe.api_key = secret
    return stripe


def _extract_price_ids_from_subscription(subscription: Any) -> List[str]:
    """
    MULTI-PRICE SUPPORT: subscriptions can contain base + add-ons.
    Return stable de-duped list of ALL price IDs.
    """
    ids: List[str] = []
    try:
        items = subscription.get("items", {}).get("data", [])  # type: ignore[union-attr]
        for it in items or []:
            price = (it or {}).get("price") or {}
            pid = price.get("id")
            if isinstance(pid, str):
                pid = pid.strip()
                if pid:
                    ids.append(pid)
    except Exception:
        return []

    seen = set()
    out: List[str] = []
    for pid in ids:
        if pid not in seen:
            seen.add(pid)
            out.append(pid)
    return out


def _is_active_subscription_status(status: Optional[str]) -> bool:
    return (status or "").strip().lower() in {"active", "trialing"}


def _status_priority(status: Optional[str]) -> int:
    s = (status or "").strip().lower()
    if s in {"active", "trialing"}:
        return 300
    if s in {"past_due", "unpaid"}:
        return 200
    if s in {"incomplete", "incomplete_expired"}:
        return 150
    if s in {"paused"}:
        return 120
    if s in {"canceled", "cancelled"}:
        return 50
    return 0


def _plan_rank(plan: str) -> int:
    p = (plan or "").strip().lower()
    if p == "enterprise":
        return 3
    if p == "pro":
        return 2
    return 1  # starter/default


def _best_entitlements_from_price_ids(price_ids: List[str]) -> Tuple[Optional[Entitlements], Optional[str]]:
    """
    MULTI-PRICE SUPPORT:
      - Evaluate entitlements across ALL price_ids
      - Keep the 'highest' plan by rank (enterprise > pro > starter)
      - Return (entitlements, primary_price_id)
    """
    best_ent: Optional[Entitlements] = None
    best_pid: Optional[str] = None
    best_rank = 0

    for pid in price_ids:
        try:
            ent = entitlements_from_stripe_price_id(pid)
            r = _plan_rank(getattr(ent, "plan", "starter"))
            if r > best_rank:
                best_rank = r
                best_ent = ent
                best_pid = pid
        except Exception:
            continue

    if best_ent is None:
        return None, (price_ids[0] if price_ids else None)

    return best_ent, best_pid


@dataclass
class SubscriptionCheckResult:
    active: bool
    reason: str
    customer_id: str
    entitlements: Optional[Entitlements] = None
    subscription_id: Optional[str] = None
    price_id: Optional[str] = None          # backward-compatible "primary"
    price_ids: Optional[List[str]] = None   # MULTI-PRICE list
    status: Optional[str] = None


def _rehydrate_entitlements(d: Any) -> Optional[Entitlements]:
    if not isinstance(d, dict):
        return None
    try:
        plan = str(d.get("plan") or "starter").strip().lower() or "starter"
        features = d.get("features") if isinstance(d.get("features"), dict) else {}
        limits = d.get("limits") if isinstance(d.get("limits"), dict) else {}
        return Entitlements(plan=plan, features=dict(features), limits=dict(limits))
    except Exception:
        return None


# ============================================================
# PLAN LIMIT CHECKS (CRASH-PROOF)
# ============================================================

def _month_epoch_range_utc() -> Tuple[int, int]:
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now.month == 12:
        nxt = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        nxt = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    return int(start.timestamp()), int(nxt.timestamp())


def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        return int(str(v).strip())
    except Exception:
        return None


def _count_payroll_runs_this_month(company_id: int) -> int:
    start, end = _month_epoch_range_utc()
    with db.engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM payroll_runs
                WHERE company_id = :cid
                  AND created_at >= :start
                  AND created_at < :end
                """
            ),
            {"cid": company_id, "start": start, "end": end},
        ).mappings().fetchone()
    return int(row["cnt"]) if row and row.get("cnt") is not None else 0


def _count_active_workers(company_id: int) -> int:
    """
    Uses a generic workers table. If your repo uses a different table name,
    keep this function and only change the SQL here (single point of change).
    """
    with db.engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM workers
                WHERE company_id = :cid
                  AND (is_active = TRUE OR is_active = 1)
                """
            ),
            {"cid": company_id},
        ).mappings().fetchone()
    return int(row["cnt"]) if row and row.get("cnt") is not None else 0


def _enforce_plan_limits(*, ent: Entitlements, feature: Optional[str]) -> Optional[Tuple[Dict[str, Any], int]]:
    """
    Returns (payload, status_code) when blocked, else None.
    Fail-closed for payroll execution if counting fails.
    """
    limits = getattr(ent, "limits", {}) or {}
    if not isinstance(limits, dict) or not limits:
        return None

    company_id = _extract_company_id()
    if company_id is None:
        return (
            {
                "error": "company_id_required",
                "message": "Provide X-Company-Id to enforce plan limits.",
            },
            401,
        )

    max_workers = _safe_int(limits.get("max_workers"))
    max_runs = _safe_int(limits.get("max_payroll_runs_per_month"))

    if max_workers is not None and max_workers >= 0:
        try:
            active_workers = _count_active_workers(int(company_id))
        except Exception as e:
            return (
                {
                    "error": "limit_check_failed",
                    "message": "Unable to validate worker limit safely. Try again or contact support.",
                    "limit": "max_workers",
                    "plan": getattr(ent, "plan", "starter"),
                    "detail": str(e),
                },
                503,
            )
        if active_workers > max_workers:
            return (
                {
                    "error": "worker_limit_exceeded",
                    "message": "Plan worker limit exceeded.",
                    "plan": getattr(ent, "plan", "starter"),
                    "allowed": max_workers,
                    "current": active_workers,
                },
                403,
            )

    if feature == "payroll_run" and max_runs is not None and max_runs >= 0:
        try:
            runs = _count_payroll_runs_this_month(int(company_id))
        except Exception as e:
            return (
                {
                    "error": "limit_check_failed",
                    "message": "Unable to validate payroll run limit safely. Try again or contact support.",
                    "limit": "max_payroll_runs_per_month",
                    "plan": getattr(ent, "plan", "starter"),
                    "detail": str(e),
                },
                503,
            )
        if runs >= max_runs:
            return (
                {
                    "error": "payroll_runs_limit_exceeded",
                    "message": "Monthly payroll run limit exceeded.",
                    "plan": getattr(ent, "plan", "starter"),
                    "allowed": max_runs,
                    "current": runs,
                },
                403,
            )

    return None


def _check_subscription_fastpath(customer_id: str) -> Optional[SubscriptionCheckResult]:
    rec = get_customer_subscription(customer_id)
    if not rec:
        return None

    status = (rec.get("status") or "").strip().lower() or None
    subscription_id = rec.get("subscription_id")
    price_id = rec.get("price_id")

    price_ids_val = rec.get("price_ids")
    price_ids: Optional[List[str]] = price_ids_val if isinstance(price_ids_val, list) else None

    active_flag = bool(rec.get("active", False))
    active = bool(active_flag and _is_active_subscription_status(status))

    ent = _rehydrate_entitlements(rec.get("entitlements")) if active else None

    if active and ent is None and price_ids:
        ent2, primary_pid = _best_entitlements_from_price_ids([p for p in price_ids if isinstance(p, str)])
        ent = ent2
        if primary_pid:
            price_id = primary_pid

    reason = "db_cache" if active else f"db_cache_inactive_{status or 'unknown'}"

    return SubscriptionCheckResult(
        active=active,
        reason=reason,
        customer_id=customer_id,
        entitlements=ent,
        subscription_id=subscription_id,
        price_id=price_id,
        price_ids=price_ids,
        status=status,
    )


def _check_subscription_via_stripe(customer_id: str) -> SubscriptionCheckResult:
    if not _stripe_enabled():
        return SubscriptionCheckResult(active=False, reason="stripe_not_configured", customer_id=customer_id)

    cached = _cache_get(customer_id)
    if cached:
        status_cached = cached.get("status")
        return SubscriptionCheckResult(
            active=bool(cached.get("active", False)),
            reason=str(cached.get("reason", "cached")),
            customer_id=customer_id,
            entitlements=_rehydrate_entitlements(cached.get("entitlements")),
            subscription_id=cached.get("subscription_id"),
            price_id=cached.get("price_id"),
            price_ids=cached.get("price_ids") if isinstance(cached.get("price_ids"), list) else None,
            status=str(status_cached).strip().lower() if isinstance(status_cached, str) and status_cached.strip() else None,
        )

    try:
        stripe = _stripe_import()

        subs = stripe.Subscription.list(customer=customer_id, status="all", limit=10)
        data = subs.get("data") or []

        if not data:
            payload = {
                "active": False,
                "reason": "no_subscription",
                "subscription_id": None,
                "price_id": None,
                "price_ids": None,
                "status": None,
                "entitlements": None,
            }
            _cache_set(customer_id, payload)
            return SubscriptionCheckResult(active=False, reason="no_subscription", customer_id=customer_id)

        def _created(s: Any) -> int:
            try:
                return int(s.get("created") or 0)
            except Exception:
                return 0

        best = sorted(
            data,
            key=lambda s: (_status_priority((s.get("status") or "").strip().lower()), _created(s)),
            reverse=True,
        )[0]

        status = (best.get("status") or "").strip().lower()
        active = _is_active_subscription_status(status)

        price_ids = _extract_price_ids_from_subscription(best)
        ent: Optional[Entitlements] = None
        primary_pid: Optional[str] = None

        if active:
            ent, primary_pid = _best_entitlements_from_price_ids(price_ids)
            if primary_pid is None and price_ids:
                primary_pid = price_ids[0]

        payload = {
            "active": active,
            "reason": "ok" if active else f"inactive_{status or 'unknown'}",
            "subscription_id": best.get("id"),
            "price_id": primary_pid,
            "price_ids": price_ids or None,
            "status": status,
            "entitlements": entitlements_to_dict(ent) if ent else None,
        }
        _cache_set(customer_id, payload)

        return SubscriptionCheckResult(
            active=active,
            reason=str(payload["reason"]),
            customer_id=customer_id,
            entitlements=ent,
            subscription_id=str(payload["subscription_id"]) if payload["subscription_id"] else None,
            price_id=primary_pid,
            price_ids=price_ids or None,
            status=status,
        )

    except Exception as e:
        payload = {
            "active": False,
            "reason": "stripe_error",
            "subscription_id": None,
            "price_id": None,
            "price_ids": None,
            "status": None,
            "entitlements": None,
            "detail": str(e),
        }
        _cache_set(customer_id, payload)
        return SubscriptionCheckResult(active=False, reason="stripe_error", customer_id=customer_id)


def _allow_when_gating_off() -> bool:
    return not subscription_required_enabled()


def require_active_subscription(_fn: Optional[F] = None, *, feature: Optional[str] = None) -> F:
    """
    Usage:
      @require_active_subscription
      @require_active_subscription()
      @require_active_subscription(feature="payroll_run")
    """

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if _allow_when_gating_off() or _bypass_enabled():
                return fn(*args, **kwargs)

            # Real package check first (payroll_only / combo grant payroll;
            # bookkeeping_only does not). Resolves the company's manual override
            # or its live Stripe subscription. Only payroll routes use this
            # decorator, so the capability is always "payroll".
            #  - True  -> correct package, allow (usage limits below are legacy
            #             tier limits that don't apply to the real packages)
            #  - False -> wrong package (e.g. bookkeeping-only) -> 402
            #  - None  -> couldn't resolve a package; fall through to the
            #             legacy Stripe/entitlement path for backward-compat.
            try:
                from utils.plan_access import (
                    _extract_company_id,
                    _needs_plan_response,
                    company_has_capability,
                )

                _cid = _extract_company_id()
                if _cid is not None:
                    _has = company_has_capability(_cid, "payroll")
                    if _has is True:
                        return fn(*args, **kwargs)
                    if _has is False:
                        return _needs_plan_response("payroll")
            except Exception:
                pass  # never let the gate itself 500 — fall through

            # HARDENED: never allow unhandled exceptions to become HTML 500
            try:
                stripe_customer_id = _resolve_stripe_customer_id()
                if not stripe_customer_id:
                    return (
                        jsonify(
                            {
                                "error": "subscription_required",
                                "message": "Missing company_id or customer_id.",
                                "hint": "Provide X-Company-Id (preferred) or X-Customer-Id.",
                            }
                        ),
                        401,
                    )

                # DB fast-path first (webhooks write here)
                res = _check_subscription_fastpath(stripe_customer_id)
                if res is None or (res is not None and res.active is False):
                    # If DB says inactive, confirm via Stripe to avoid stale webhook state
                    res = _check_subscription_via_stripe(stripe_customer_id)

                if not res.active:
                    return (
                        jsonify(
                            {
                                "error": "subscription_inactive",
                                "message": "Active subscription required.",
                                "reason": res.reason,
                                "customer_id": stripe_customer_id,
                                "status": res.status,
                                "subscription_id": res.subscription_id,
                            }
                        ),
                        402,
                    )

                # Resolve entitlements (required for both feature gating and limits)
                ent = res.entitlements
                if ent is None:
                    try:
                        if res.price_ids:
                            ent2, primary_pid = _best_entitlements_from_price_ids([p for p in res.price_ids if isinstance(p, str)])
                            ent = ent2 or entitlements_from_stripe_price_id(primary_pid or res.price_id)
                        else:
                            ent = entitlements_from_stripe_price_id(res.price_id)
                    except Exception as e:
                        return (
                            jsonify(
                                {
                                    "error": "entitlements_unavailable",
                                    "message": "Unable to resolve plan entitlements.",
                                    "customer_id": stripe_customer_id,
                                    "detail": str(e),
                                }
                            ),
                            503,
                        )

                # PLAN LIMIT ENFORCEMENT (before heavy work)
                blocked = _enforce_plan_limits(ent=ent, feature=feature)
                if blocked is not None:
                    payload, code = blocked
                    return jsonify(payload), code

                # FEATURE GATING
                if feature:
                    if not feature_enabled(ent, feature):
                        return (
                            jsonify(
                                {
                                    "error": "feature_not_entitled",
                                    "message": "Your plan does not include this feature.",
                                    "feature": feature,
                                    "plan": ent.plan,
                                }
                            ),
                            403,
                        )

                return fn(*args, **kwargs)

            except Exception as e:
                return (
                    jsonify(
                        {
                            "error": "subscription_gate_error",
                            "message": "Subscription gate failure.",
                            "detail": str(e),
                        }
                    ),
                    503,
                )

        return cast(F, wrapper)

    if _fn is None:
        return cast(F, decorator)
    return decorator(_fn)


if __name__ == "__main__":
    os.environ["SUBSCRIPTION_REQUIRED"] = "0"
    assert subscription_required_enabled() is False

    os.environ["SUBSCRIPTION_REQUIRED"] = "1"
    assert subscription_required_enabled() is True

    os.environ["SUBSCRIPTION_BYPASS"] = "1"
    assert _bypass_enabled() is True

    os.environ["SUBSCRIPTION_BYPASS"] = "0"
    assert _bypass_enabled() is False

    print("billing/subscription_gate.py OK")

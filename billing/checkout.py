# File: billing/checkout.py
# Purpose: Stripe Checkout entrypoints
# Purpose: Creates Checkout Sessions for subscriptions
# Import expectation (in app.py):
#     from billing.checkout import billing_bp
# Date: 2026-01-24
# Status: Production-grade
# Status: Uses persistent company->Stripe customer mapping
# Status: Correct env validation
# Status: Idempotent sessions

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, redirect, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

from billing.customers import get_company_customer, get_or_create_company_customer

billing_bp = Blueprint("billing", __name__, url_prefix="/billing")


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name, default)
    if val is None:
        return None
    val = val.strip()
    return val if val else None


def _truthy(v: Optional[str]) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        i = int(v)
        return i if i >= 0 else default
    except Exception:
        return default


def _json_error(
    message: str,
    status: int = 400,
    **extra: Any,
) -> Tuple[Any, int]:
    payload: Dict[str, Any] = {"error": message}
    payload.update(extra)
    return jsonify(payload), status


def _stripe_client():
    try:
        import stripe  # type: ignore
    except Exception as e:
        raise RuntimeError(f"Stripe library not available: {e}") from e

    secret = _get_env("STRIPE_SECRET_KEY")
    if not secret:
        raise RuntimeError("Missing STRIPE_SECRET_KEY env var")

    if (
        secret in {"sk_live", "sk_test"}
        or not (
            secret.startswith("sk_live_")
            or secret.startswith("sk_test_")
        )
    ):
        raise RuntimeError(
            "Invalid STRIPE_SECRET_KEY format "
            "(must start with sk_live_ or sk_test_)"
        )

    stripe.api_key = secret
    return stripe


def _base_url() -> str:
    explicit = _get_env("BASE_URL") or _get_env("APP_BASE_URL")
    if explicit:
        return explicit.rstrip("/")
    return request.host_url.rstrip("/")


def _frontend_base_url() -> str:
    """
    Where Stripe should send the customer back to. This must be the app
    site, never the API host (request.host_url here is api.ledgerhaul.com,
    which has no pages). Hard default to the real site because env vars
    have proven unreliable on this hosting setup.
    """
    explicit = (
        _get_env("FRONTEND_BASE_URL")
        or _get_env("BASE_URL")
        or _get_env("APP_BASE_URL")
    )
    if explicit and "api." not in explicit:
        return explicit.rstrip("/")
    return "https://www.ledgerhaul.com"


def _require_company_id(data: Dict[str, Any]) -> int:
    """
    REQUIRED for production: checkout must bind to a company_id.
    Prefers JWT identity to prevent XSS-based company_id spoofing.
    """
    # Prefer JWT identity — prevents localStorage spoofing attack
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        if isinstance(identity, dict) and identity.get("company_id"):
            return int(identity["company_id"])
    except Exception:
        pass

    cid = (
        request.headers.get("X-Company-Id")
        or request.args.get("company_id")
        or data.get("company_id")
    )
    if cid is None or str(cid).strip() == "":
        raise ValueError(
            "Missing company_id "
            "(X-Company-Id header, query, or JSON)."
        )
    try:
        v = int(str(cid).strip())
        if v < 0:
            raise ValueError("company_id must be a non-negative integer.")
        return v
    except Exception:
        raise ValueError("company_id must be an integer.")


def _pricing_from_env() -> Dict[str, Dict[str, Optional[str]]]:
    """
    Uses your existing env naming standard.
    """
    return {
        "combo": {
            "base_price_id": _get_env("STRIPE_COMBO_PRICE_ID"),
            "per_employee_price_id": _get_env(
                "STRIPE_COMBO_PER_EMPLOYEE_PRICE_ID"
            ),
        },
        "payroll_only": {
            "base_price_id": _get_env("STRIPE_PAYROLL_PRICE_ID"),
            "per_employee_price_id": _get_env(
                "STRIPE_PAYROLL_PER_EMPLOYEE_PRICE_ID"
            ),
        },
        "bookkeeping_only": {
            "base_price_id": _get_env("STRIPE_BOOKKEEPING_PRICE_ID"),
            "per_employee_price_id": None,
        },
    }


# ------------------------------------------------------------------
# Stripe catalog auto-discovery
#
# The hosting dashboard has repeatedly failed to persist STRIPE_*_PRICE_ID
# env vars into the running process, leaving checkout pointed at stale
# price ids. Rather than depend on env vars at all, resolve the plans
# directly from the connected Stripe account's own product catalog:
# active recurring prices whose product name contains "combo", "payroll"
# or "bookkeep". Env vars, when present AND valid, still win.
# ------------------------------------------------------------------
_CATALOG_TTL_SECONDS = 600
_catalog_cache: Dict[str, Any] = {"at": 0.0, "pricing": None}


def _plan_for_product_name(name: str) -> Optional[str]:
    n = (name or "").lower()
    if "combo" in n:
        return "combo"
    if "payroll" in n:
        return "payroll_only"
    if "bookkeep" in n:
        return "bookkeeping_only"
    return None


def _pricing_from_catalog(stripe, force: bool = False) -> Dict[str, Dict[str, Optional[str]]]:
    """
    Resolve plan prices from Stripe's live catalog. Cached for 10 minutes.
    Per plan: base = highest-amount active recurring price (newest wins on
    ties), per-employee = the cheaper second price when one exists.
    """
    now = time.monotonic()
    cached = _catalog_cache.get("pricing")
    if not force and cached and (now - _catalog_cache["at"]) < _CATALOG_TTL_SECONDS:
        return cached

    buckets: Dict[str, List[Any]] = {}
    prices = stripe.Price.list(active=True, limit=100, expand=["data.product"])
    for p in prices.auto_paging_iter():
        if not p.get("recurring"):
            continue
        product = p.get("product") or {}
        if isinstance(product, str) or not product.get("active", True):
            continue
        plan = _plan_for_product_name(product.get("name") or "")
        if plan:
            buckets.setdefault(plan, []).append(p)

    pricing: Dict[str, Dict[str, Optional[str]]] = {
        "combo": {"base_price_id": None, "per_employee_price_id": None},
        "payroll_only": {"base_price_id": None, "per_employee_price_id": None},
        "bookkeeping_only": {"base_price_id": None, "per_employee_price_id": None},
    }
    def _looks_per_driver(p: Any) -> bool:
        label = f"{p.get('nickname') or ''} {p.get('lookup_key') or ''}".lower()
        return any(w in label for w in ("driver", "employee", "seat", "per_"))

    for plan, plist in buckets.items():
        # Prices explicitly labelled per-driver/seat are never the base.
        labelled = [p for p in plist if _looks_per_driver(p)]
        candidates = [p for p in plist if not _looks_per_driver(p)] or plist
        candidates.sort(
            key=lambda p: (int(p.get("unit_amount") or 0), int(p.get("created") or 0)),
            reverse=True,
        )
        pricing[plan]["base_price_id"] = candidates[0]["id"]
        if plan != "bookkeeping_only":
            if labelled:
                pricing[plan]["per_employee_price_id"] = labelled[0]["id"]
            elif len(candidates) > 1:
                pricing[plan]["per_employee_price_id"] = candidates[-1]["id"]

    _catalog_cache["at"] = now
    _catalog_cache["pricing"] = pricing
    return pricing


def _effective_pricing(stripe, force_catalog: bool = False) -> Dict[str, Dict[str, Optional[str]]]:
    """
    The Stripe catalog is the source of truth — whatever the connected
    account's products say right now wins. Env vars only fill plans the
    catalog could not resolve (missing/renamed product): they hold stale
    ids from earlier configurations too easily to be trusted first.
    """
    env_pricing = _pricing_from_env()
    catalog = _pricing_from_catalog(stripe, force=force_catalog)
    merged: Dict[str, Dict[str, Optional[str]]] = {}
    for plan in ("combo", "payroll_only", "bookkeeping_only"):
        env_cfg = env_pricing.get(plan) or {}
        cat_cfg = catalog.get(plan) or {}
        env_base = env_cfg.get("base_price_id")
        env_per_emp = env_cfg.get("per_employee_price_id")
        merged[plan] = {
            "base_price_id": cat_cfg.get("base_price_id")
            or (env_base if (env_base or "").startswith("price_") else None),
            "per_employee_price_id": cat_cfg.get("per_employee_price_id")
            or (env_per_emp if (env_per_emp or "").startswith("price_") else None),
        }
    return merged


def _is_no_such_price_error(err: Exception) -> bool:
    return "no such price" in str(err).lower()


def _params_signature(params: Dict[str, Any]) -> str:
    import hashlib
    import json

    blob = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:10]


def _create_checkout_session_compat(stripe, kwargs: Dict[str, Any], idem_key: str):
    """
    Create a Checkout Session with Stripe's Adaptive Pricing disabled so
    international customers see USD only (no local-currency picker).
    Falls back without the parameter for accounts/API versions that don't
    recognise it.

    The idempotency key embeds a hash of the exact parameters sent: Stripe
    permanently binds a key to its first parameter set, so any change
    (new URLs, new flags, retry without adaptive_pricing) must produce a
    fresh key or Stripe rejects the request for up to 24 hours.
    """
    params = {**kwargs, "adaptive_pricing": {"enabled": False}}
    try:
        return stripe.checkout.Session.create(
            **params,
            idempotency_key=f"{idem_key}_{_params_signature(params)}",
        )
    except Exception as e:
        msg = str(e).lower()
        if "adaptive_pricing" in msg and ("unknown parameter" in msg or "received unknown" in msg):
            return stripe.checkout.Session.create(
                **kwargs,
                idempotency_key=f"{idem_key}_{_params_signature(kwargs)}",
            )
        raise


def _line_items_for_plan(
    pricing: Dict[str, Dict[str, Optional[str]]],
    plan_key: str,
    employees: int,
) -> List[Dict[str, Any]]:
    cfg = pricing.get(plan_key) or {}
    base = cfg.get("base_price_id")
    if not base or not str(base).startswith("price_"):
        raise RuntimeError(
            f"No active Stripe price found for plan '{plan_key}'. Create an "
            "active recurring product in Stripe whose name contains "
            "Combo/Payroll/Bookkeeping, or set "
            f"{_env_name_for_plan_base(plan_key)}."
        )
    items: List[Dict[str, Any]] = [{"price": base, "quantity": 1}]
    per_emp = cfg.get("per_employee_price_id")
    if per_emp and employees > 0:
        items.append({"price": per_emp, "quantity": employees})
    return items


def _validate_price_id(pid: Optional[str], env_name: str) -> str:
    if not pid:
        raise RuntimeError(f"Missing {env_name} env var")
    if not pid.startswith("price_"):
        raise RuntimeError(
            f"Invalid {env_name} (expected price_...): {pid}"
        )
    return pid


def _env_name_for_plan_base(plan_key: str) -> str:
    return {
        "combo": "STRIPE_COMBO_PRICE_ID",
        "payroll_only": "STRIPE_PAYROLL_PRICE_ID",
        "bookkeeping_only": "STRIPE_BOOKKEEPING_PRICE_ID",
    }.get(plan_key, f"STRIPE_{plan_key.upper()}_PRICE_ID")


def _env_name_for_plan_per_emp(plan_key: str) -> str:
    return {
        "combo": "STRIPE_COMBO_PER_EMPLOYEE_PRICE_ID",
        "payroll_only": "STRIPE_PAYROLL_PER_EMPLOYEE_PRICE_ID",
    }.get(plan_key, f"STRIPE_{plan_key.upper()}_PER_EMPLOYEE_PRICE_ID")


def _resolve_company_customer_id(
    *,
    company_id: int,
    email: Optional[str],
    name: Optional[str],
) -> str:
    """
    Production rule: Checkout must use the company-owned Stripe customer id
    persisted in Postgres (billing/customers.py).
    """
    rec = get_or_create_company_customer(
        company_id=company_id,
        email=email,
        name=name,
    )
    cid = (rec.get("stripe_customer_id") or "").strip()
    if not cid.startswith("cus_"):
        raise RuntimeError("Invalid stripe_customer_id resolved for company")
    return cid


@billing_bp.get("/health")
def billing_health():
    return jsonify({"status": "ok"}), 200


@billing_bp.get("/debug-prices")
def billing_debug_prices():
    """
    Temporary diagnostic: shows the env-configured price IDs, what the
    Stripe catalog auto-discovery resolves, and the effective merge that
    checkout will actually use. Price IDs are not secret (Stripe
    secret/webhook keys are never exposed here).
    """
    secret = _get_env("STRIPE_SECRET_KEY") or ""
    payload: Dict[str, Any] = {
        "stripe_mode": "live" if secret.startswith("sk_live_") else ("test" if secret.startswith("sk_test_") else "unset"),
        "pricing_from_env": _pricing_from_env(),
    }
    try:
        stripe = _stripe_client()
        payload["pricing_from_catalog"] = _pricing_from_catalog(stripe, force=True)
        payload["pricing_effective"] = _effective_pricing(stripe)
    except Exception as e:
        payload["catalog_error"] = str(e)
    return jsonify(payload), 200


def _plan_key_for_price(price_id: str) -> Optional[str]:
    if not price_id:
        return None
    # Check env-configured ids first, then the auto-discovered catalog.
    candidates = [_pricing_from_env()]
    try:
        candidates.append(_pricing_from_catalog(_stripe_client()))
    except Exception:
        pass
    for pricing in candidates:
        for key, cfg in pricing.items():
            if price_id in {cfg.get("base_price_id"), cfg.get("per_employee_price_id")}:
                return key
    return None


@billing_bp.get("/status")
def billing_status():
    """
    GET /billing/status

    Returns the company's current subscription state so the app's Billing
    page can show the active plan (or none).

    Output:
      {
        "status": "active|trialing|past_due|canceled|none",
        "plan": "combo|payroll_only|bookkeeping_only|null",
        "current_period_end": "ISO8601|null",
        "cancel_at_period_end": bool,
        "stripe_customer_id": "cus_...|null"
      }
    """
    try:
        company_id = _require_company_id({})
    except Exception as e:
        return _json_error("invalid_request", 400, detail=str(e))

    none_payload = {
        "status": "none",
        "plan": None,
        "current_period_end": None,
        "cancel_at_period_end": False,
        "stripe_customer_id": None,
    }

    try:
        rec = get_company_customer(company_id)
    except Exception:
        rec = None
    customer_id = (rec or {}).get("stripe_customer_id")
    if not customer_id:
        return jsonify(none_payload), 200

    none_payload["stripe_customer_id"] = customer_id

    try:
        stripe = _stripe_client()
        subs = stripe.Subscription.list(
            customer=customer_id,
            status="all",
            limit=10,
        )
        items = subs.get("data") or []
        # Prefer a live subscription over historical/canceled ones
        rank = {"active": 0, "trialing": 1, "past_due": 2, "unpaid": 3, "canceled": 4}
        items.sort(key=lambda s: rank.get(s.get("status"), 9))
        if not items:
            return jsonify(none_payload), 200

        sub = items[0]
        plan_key = None
        for li in (sub.get("items", {}).get("data") or []):
            plan_key = _plan_key_for_price((li.get("price") or {}).get("id") or "")
            if plan_key:
                break

        period_end = sub.get("current_period_end")
        from datetime import datetime, timezone
        period_end_iso = (
            datetime.fromtimestamp(int(period_end), tz=timezone.utc).isoformat()
            if period_end
            else None
        )

        return jsonify(
            {
                "status": sub.get("status") or "none",
                "plan": plan_key,
                "current_period_end": period_end_iso,
                "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
                "stripe_customer_id": customer_id,
            }
        ), 200
    except Exception as e:
        return _json_error("billing_status_failed", 500, detail=str(e))


# ============================================================
# Primary: Plan-based subscription checkout (JSON)
# ============================================================
@billing_bp.post("/checkout")
def checkout_create():
    """
    POST /billing/checkout

    Body:
      {
        "company_id": 0,
        "plan": "combo|payroll_only|bookkeeping_only",
        "employees": 0,
        "email": "...",
        "name": "..."
      }

    Returns:
      {
        "checkout_url": "https://checkout.stripe.com/...",
        "id": "cs_..."
      }
    """
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return _json_error("Invalid JSON body. Send application/json.", 400)

    plan_key = str(data.get("plan") or "").strip()
    employees = _safe_int(data.get("employees", 0), 0)

    customer_email = (
        data.get("email")
        or request.args.get("email")
        or ""
    )
    customer_email = customer_email.strip() or None

    customer_name = (
        data.get("name")
        or request.args.get("name")
        or ""
    )
    customer_name = customer_name.strip() or None

    pricing = _pricing_from_env()
    if plan_key not in pricing:
        return _json_error(
            "Invalid plan",
            400,
            allowed=list(pricing.keys()),
        )

    try:
        company_id = _require_company_id(data)
    except Exception as e:
        return _json_error("invalid_request", 400, detail=str(e))

    base = _frontend_base_url()
    success_url = _get_env(
        "STRIPE_SUCCESS_URL",
        f"{base}/billing?checkout=success",
    )
    cancel_url = _get_env(
        "STRIPE_CANCEL_URL",
        f"{base}/billing",
    )

    allow_promo = _truthy(
        _get_env("STRIPE_CHECKOUT_ALLOW_PROMO_CODES", "0")
    )
    automatic_tax = _truthy(
        _get_env("STRIPE_CHECKOUT_AUTOMATIC_TAX", "0")
    )
    require_billing_address = _truthy(
        _get_env("STRIPE_REQUIRE_BILLING_ADDRESS", "0")
    )
    tax_id_collection = _truthy(
        _get_env("STRIPE_TAX_ID_COLLECTION", "0")
    )

    try:
        stripe = _stripe_client()

        customer_id = _resolve_company_customer_id(
            company_id=company_id,
            email=customer_email,
            name=customer_name,
        )

        session_kwargs: Dict[str, Any] = {
            "mode": "subscription",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "allow_promotion_codes": allow_promo,
            "customer": customer_id,
            "metadata": {
                "company_id": str(company_id),
                "plan": plan_key,
                "employees": str(employees),
                "app": "LedgerHaul",
            },
        }

        if automatic_tax:
            session_kwargs["automatic_tax"] = {"enabled": True}
        if require_billing_address:
            session_kwargs["billing_address_collection"] = "required"
        if tax_id_collection:
            session_kwargs["tax_id_collection"] = {"enabled": True}

        def _create_session(items: List[Dict[str, Any]]):
            # Include the price ids in the idempotency key: a retry after a
            # stale-price failure uses different line items, and Stripe
            # rejects reusing a key with changed parameters.
            key_suffix = "-".join(str(li["price"])[-8:] for li in items)
            return _create_checkout_session_compat(
                stripe,
                {**session_kwargs, "line_items": items},
                (
                    "ledgerhaul_checkout_company_"
                    f"{company_id}_plan_{plan_key}_emp_{employees}_{key_suffix}"
                ),
            )

        line_items = _line_items_for_plan(
            _effective_pricing(stripe), plan_key, employees
        )
        try:
            session = _create_session(line_items)
        except Exception as first_err:
            if not _is_no_such_price_error(first_err):
                raise
            # Env var pointed at a stale/wrong-mode price. Re-resolve from
            # the live Stripe catalog (env ignored) and retry once.
            catalog_only = _pricing_from_catalog(stripe, force=True)
            retry_items = _line_items_for_plan(catalog_only, plan_key, employees)
            if retry_items == line_items:
                raise
            session = _create_session(retry_items)

        return jsonify(
            {
                "checkout_url": session.get("url"),
                "id": session.get("id"),
            }
        ), 200

    except Exception as e:
        return _json_error(
            "stripe_checkout_failed",
            500,
            detail=str(e),
            company_id=company_id,
            plan=plan_key,
            employees=employees,
            base_url=base,
        )


# ============================================================
# Browser-friendly: Plan-based subscription checkout (redirect)
# ============================================================
@billing_bp.get("/checkout-link")
def checkout_link():
    """
    GET /billing/checkout-link
    ?company_id=0
    &plan=combo
    &employees=0
    &email=you@domain.com
    &name=LedgerHaul%20User

    Redirects to Stripe Checkout.
    Surfaces Stripe errors as JSON (500).
    """
    plan_key = (request.args.get("plan") or "").strip()
    employees = _safe_int(request.args.get("employees", 0), 0)

    pricing = _pricing_from_env()
    if plan_key not in pricing:
        return _json_error(
            "Invalid plan",
            400,
            allowed=list(pricing.keys()),
        )

    data: Dict[str, Any] = {}
    try:
        company_id = _require_company_id(data)
    except Exception as e:
        return _json_error("invalid_request", 400, detail=str(e))

    customer_email = (request.args.get("email") or "").strip() or None
    customer_name = (request.args.get("name") or "").strip() or None

    base = _frontend_base_url()
    success_url = _get_env(
        "STRIPE_SUCCESS_URL",
        f"{base}/billing?checkout=success",
    )
    cancel_url = _get_env(
        "STRIPE_CANCEL_URL",
        f"{base}/billing",
    )

    try:
        stripe = _stripe_client()

        customer_id = _resolve_company_customer_id(
            company_id=company_id,
            email=customer_email,
            name=customer_name,
        )

        def _create_session(items: List[Dict[str, Any]]):
            key_suffix = "-".join(str(li["price"])[-8:] for li in items)
            return _create_checkout_session_compat(
                stripe,
                {
                    "mode": "subscription",
                    "line_items": items,
                    "success_url": success_url,
                    "cancel_url": cancel_url,
                    "allow_promotion_codes": _truthy(
                        _get_env("STRIPE_CHECKOUT_ALLOW_PROMO_CODES", "0")
                    ),
                    "customer": customer_id,
                    "metadata": {
                        "company_id": str(company_id),
                        "plan": plan_key,
                        "employees": str(employees),
                        "app": "LedgerHaul",
                    },
                },
                (
                    "ledgerhaul_checkoutlink_company_"
                    f"{company_id}_plan_{plan_key}_emp_{employees}_{key_suffix}"
                ),
            )

        line_items = _line_items_for_plan(
            _effective_pricing(stripe), plan_key, employees
        )
        try:
            session = _create_session(line_items)
        except Exception as first_err:
            if not _is_no_such_price_error(first_err):
                raise
            catalog_only = _pricing_from_catalog(stripe, force=True)
            retry_items = _line_items_for_plan(catalog_only, plan_key, employees)
            if retry_items == line_items:
                raise
            session = _create_session(retry_items)

        return redirect(session.get("url"), code=302)

    except Exception as e:
        return _json_error(
            "stripe_checkout_failed",
            500,
            detail=str(e),
            company_id=company_id,
            plan=plan_key,
            employees=employees,
            base_url=base,
        )


# ============================================================
# Back-compat: single-price session endpoint
# ============================================================
@billing_bp.post("/checkout/session")
def create_checkout_session():
    """
    Back-compat endpoint.
    Production rule enforced:
    must provide company_id;
    customer is resolved from company mapping.
    """
    price_id = _get_env("STRIPE_PRICE_ID")
    if not price_id:
        return _json_error("Missing STRIPE_PRICE_ID env var", 500)

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return _json_error("Invalid JSON body. Send application/json.", 400)

    try:
        company_id = _require_company_id(data)
    except Exception as e:
        return _json_error("invalid_request", 400, detail=str(e))

    customer_email = (
        data.get("email")
        or request.args.get("email")
        or ""
    )
    customer_email = customer_email.strip() or None

    customer_name = (
        data.get("name")
        or request.args.get("name")
        or ""
    )
    customer_name = customer_name.strip() or None

    base = _frontend_base_url()
    success_url = _get_env(
        "STRIPE_SUCCESS_URL",
        f"{base}/dashboard?checkout=success",
    )
    cancel_url = _get_env(
        "STRIPE_CANCEL_URL",
        f"{base}/billing",
    )

    allow_promo = _truthy(
        _get_env("STRIPE_CHECKOUT_ALLOW_PROMO_CODES", "0")
    )
    automatic_tax = _truthy(
        _get_env("STRIPE_CHECKOUT_AUTOMATIC_TAX", "0")
    )
    require_billing_address = _truthy(
        _get_env("STRIPE_REQUIRE_BILLING_ADDRESS", "0")
    )
    tax_id_collection = _truthy(
        _get_env("STRIPE_TAX_ID_COLLECTION", "0")
    )

    metadata_in = data.get("metadata")
    metadata: Optional[Dict[str, str]] = None
    if isinstance(metadata_in, dict):
        metadata = {str(k): str(v) for k, v in metadata_in.items()}

    cr_field = (
        _get_env("STRIPE_CLIENT_REFERENCE_ID_FIELD", "company_id")
        or "company_id"
    ).strip()
    client_reference_id = None
    if cr_field and isinstance(data.get(cr_field), (str, int)):
        client_reference_id = str(data.get(cr_field)).strip() or None
    if client_reference_id is None:
        client_reference_id = str(company_id)

    try:
        stripe = _stripe_client()

        customer_id = _resolve_company_customer_id(
            company_id=company_id,
            email=customer_email,
            name=customer_name,
        )

        session_kwargs: Dict[str, Any] = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "allow_promotion_codes": allow_promo,
            "customer": customer_id,
            "client_reference_id": client_reference_id,
            "metadata": {
                "company_id": str(company_id),
                "app": "LedgerHaul",
                **(metadata or {}),
            },
        }

        if automatic_tax:
            session_kwargs["automatic_tax"] = {"enabled": True}
        if require_billing_address:
            session_kwargs["billing_address_collection"] = "required"
        if tax_id_collection:
            session_kwargs["tax_id_collection"] = {"enabled": True}

        session = stripe.checkout.Session.create(
            **session_kwargs,
            idempotency_key=(
                "ledgerhaul_checkout_session_company_"
                f"{company_id}_price_{price_id}"
            ),
        )
        return jsonify(
            {
                "id": session.get("id"),
                "url": session.get("url"),
            }
        ), 200

    except Exception as e:
        return _json_error(
            "Failed to create checkout session",
            500,
            detail=str(e),
            company_id=company_id,
        )


@billing_bp.post("/checkout/session/one-time")
def create_one_time_checkout_session():
    """
    One-time payment endpoint.
    Production rule enforced:
    must provide company_id;
    customer is resolved from company mapping.
    """
    price_id = _get_env("STRIPE_ONE_TIME_PRICE_ID")
    if not price_id:
        return _json_error("Missing STRIPE_ONE_TIME_PRICE_ID env var", 500)

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return _json_error("Invalid JSON body. Send application/json.", 400)

    try:
        company_id = _require_company_id(data)
    except Exception as e:
        return _json_error("invalid_request", 400, detail=str(e))

    customer_email = (
        data.get("email")
        or request.args.get("email")
        or ""
    )
    customer_email = customer_email.strip() or None

    customer_name = (
        data.get("name")
        or request.args.get("name")
        or ""
    )
    customer_name = customer_name.strip() or None

    base = _frontend_base_url()
    success_url = _get_env(
        "STRIPE_SUCCESS_URL",
        f"{base}/dashboard?checkout=success",
    )
    cancel_url = _get_env(
        "STRIPE_CANCEL_URL",
        f"{base}/billing",
    )

    automatic_tax = _truthy(
        _get_env("STRIPE_CHECKOUT_AUTOMATIC_TAX", "0")
    )
    require_billing_address = _truthy(
        _get_env("STRIPE_REQUIRE_BILLING_ADDRESS", "0")
    )
    tax_id_collection = _truthy(
        _get_env("STRIPE_TAX_ID_COLLECTION", "0")
    )

    metadata_in = data.get("metadata")
    metadata: Optional[Dict[str, str]] = None
    if isinstance(metadata_in, dict):
        metadata = {str(k): str(v) for k, v in metadata_in.items()}

    try:
        stripe = _stripe_client()

        customer_id = _resolve_company_customer_id(
            company_id=company_id,
            email=customer_email,
            name=customer_name,
        )

        session_kwargs: Dict[str, Any] = {
            "mode": "payment",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "customer": customer_id,
            "metadata": {
                "company_id": str(company_id),
                "app": "LedgerHaul",
                **(metadata or {}),
            },
        }

        if automatic_tax:
            session_kwargs["automatic_tax"] = {"enabled": True}
        if require_billing_address:
            session_kwargs["billing_address_collection"] = "required"
        if tax_id_collection:
            session_kwargs["tax_id_collection"] = {"enabled": True}

        session = stripe.checkout.Session.create(
            **session_kwargs,
            idempotency_key=(
                "ledgerhaul_checkout_onetime_company_"
                f"{company_id}_price_{price_id}"
            ),
        )
        return jsonify(
            {
                "id": session.get("id"),
                "url": session.get("url"),
            }
        ), 200

    except Exception as e:
        return _json_error(
            "Failed to create one-time checkout session",
            500,
            detail=str(e),
            company_id=company_id,
        )


if __name__ == "__main__":
    assert billing_bp.name == "billing"
    print("billing/checkout.py OK")

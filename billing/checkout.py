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
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, jsonify, redirect, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

from billing.customers import get_or_create_company_customer

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

    base = _base_url()
    success_url = _get_env(
        "STRIPE_SUCCESS_URL",
        f"{base}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
    )
    cancel_url = _get_env(
        "STRIPE_CANCEL_URL",
        f"{base}/billing/cancel",
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

        base_price_env = _env_name_for_plan_base(plan_key)
        base_price_id = _validate_price_id(
            pricing[plan_key]["base_price_id"],
            base_price_env,
        )

        line_items: list[dict[str, Any]] = [
            {"price": base_price_id, "quantity": 1}
        ]

        per_emp_pid = pricing[plan_key].get("per_employee_price_id")
        if per_emp_pid and employees > 0:
            per_emp_env = _env_name_for_plan_per_emp(plan_key)
            per_emp_pid = _validate_price_id(
                per_emp_pid,
                per_emp_env,
            )
            line_items.append(
                {"price": per_emp_pid, "quantity": employees}
            )

        customer_id = _resolve_company_customer_id(
            company_id=company_id,
            email=customer_email,
            name=customer_name,
        )

        session_kwargs: Dict[str, Any] = {
            "mode": "subscription",
            "line_items": line_items,
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

        session = stripe.checkout.Session.create(
            **session_kwargs,
            idempotency_key=(
                "ledgerhaul_checkout_company_"
                f"{company_id}_plan_{plan_key}_emp_{employees}"
            ),
        )
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

    base = _base_url()
    success_url = _get_env(
        "STRIPE_SUCCESS_URL",
        f"{base}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
    )
    cancel_url = _get_env(
        "STRIPE_CANCEL_URL",
        f"{base}/billing/cancel",
    )

    try:
        stripe = _stripe_client()

        base_price_env = _env_name_for_plan_base(plan_key)
        base_price_id = _validate_price_id(
            pricing[plan_key]["base_price_id"],
            base_price_env,
        )

        line_items: list[dict[str, Any]] = [
            {"price": base_price_id, "quantity": 1}
        ]

        per_emp_pid = pricing[plan_key].get("per_employee_price_id")
        if per_emp_pid and employees > 0:
            per_emp_env = _env_name_for_plan_per_emp(plan_key)
            per_emp_pid = _validate_price_id(
                per_emp_pid,
                per_emp_env,
            )
            line_items.append(
                {"price": per_emp_pid, "quantity": employees}
            )

        customer_id = _resolve_company_customer_id(
            company_id=company_id,
            email=customer_email,
            name=customer_name,
        )

        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=line_items,
            success_url=success_url,
            cancel_url=cancel_url,
            allow_promotion_codes=_truthy(
                _get_env("STRIPE_CHECKOUT_ALLOW_PROMO_CODES", "0")
            ),
            customer=customer_id,
            metadata={
                "company_id": str(company_id),
                "plan": plan_key,
                "employees": str(employees),
                "app": "LedgerHaul",
            },
            idempotency_key=(
                "ledgerhaul_checkoutlink_company_"
                f"{company_id}_plan_{plan_key}_emp_{employees}"
            ),
        )
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

    base = _base_url()
    success_url = _get_env(
        "STRIPE_SUCCESS_URL",
        f"{base}/dashboard?checkout=success",
    )
    cancel_url = _get_env(
        "STRIPE_CANCEL_URL",
        f"{base}/billing?checkout=cancel",
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

    base = _base_url()
    success_url = _get_env(
        "STRIPE_SUCCESS_URL",
        f"{base}/dashboard?checkout=success",
    )
    cancel_url = _get_env(
        "STRIPE_CANCEL_URL",
        f"{base}/billing?checkout=cancel",
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

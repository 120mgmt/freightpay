# File: billing/customer_portal.py
# Purpose: Stripe Customer Portal
# Purpose: manage subscription, payment methods, invoices
# Status: FULL deployment-ready
# Status: production hardened, company-bound customer resolution
# Date: 2026-01-24

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, current_app, jsonify, request

from billing.customers import get_or_create_company_customer

portal_bp = Blueprint("portal", __name__, url_prefix="/billing/portal")


# -------------------------
# Helpers
# -------------------------
def _json_error(
    message: str,
    status: int = 400,
    **extra: Any,
) -> Tuple[Any, int]:
    payload: Dict[str, Any] = {"error": message}
    payload.update(extra)
    return jsonify(payload), status


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name, default)
    if val is None:
        return None
    val = val.strip()
    return val if val else None


def _stripe_client():
    """
    Returns a configured Stripe client.
    Hard-fails if Stripe or required env vars are missing.
    """
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


def _require_company_id(data: Dict[str, Any]) -> int:
    """
    Production rule: portal session must be bound to a company_id.
    Allows company_id=0 (your current environment uses it).
    """
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


def _resolve_company_customer_id(
    *,
    company_id: int,
    email: Optional[str],
    name: Optional[str],
) -> str:
    rec = get_or_create_company_customer(
        company_id=company_id,
        email=email,
        name=name,
    )
    cid = (rec.get("stripe_customer_id") or "").strip()
    if not cid.startswith("cus_"):
        raise RuntimeError("Invalid stripe_customer_id resolved for company")
    return cid


def _get_return_url() -> str:
    """
    Determines a safe return URL after portal exit.
    Priority:
      1) STRIPE_PORTAL_RETURN_URL env var
      2) BASE_URL env var + /dashboard
      3) request.host_url + /dashboard
      4) "/"
    """
    env_url = _get_env("STRIPE_PORTAL_RETURN_URL")
    if env_url:
        return env_url

    base_url = _get_env("BASE_URL") or _get_env("APP_BASE_URL")
    if base_url:
        return f"{base_url.rstrip('/')}/dashboard"

    try:
        base = request.host_url.rstrip("/")
        return f"{base}/dashboard"
    except Exception:
        return "/"


# -------------------------
# Routes
# -------------------------
@portal_bp.route("/health", methods=["GET"])
def portal_health():
    return jsonify({"status": "ok"}), 200


@portal_bp.route("/session", methods=["POST"])
def create_customer_portal_session():
    """
    Creates a Stripe Customer Portal session so customers can:
      - Manage subscription
      - Update payment methods
      - View invoices

    REQUIRED ENV:
      - STRIPE_SECRET_KEY

    INPUT:
      - company_id (required): header X-Company-Id OR JSON body OR query param
      - optional email/name (used only if we must create/recover customer):
          JSON: { "email": "...", "name": "..." } OR query params

    OUTPUT:
      { "url": "<stripe portal url>" }
    """
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return _json_error(
            "Invalid JSON body. Send application/json.",
            400,
        )

    try:
        company_id = _require_company_id(data)
    except Exception as e:
        return _json_error("invalid_request", 400, detail=str(e))

    email = (
        (data.get("email") or request.args.get("email") or "").strip()
        or None
    )
    name = (
        (data.get("name") or request.args.get("name") or "").strip()
        or None
    )

    try:
        stripe = _stripe_client()

        customer_id = _resolve_company_customer_id(
            company_id=company_id,
            email=email,
            name=name,
        )

        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=_get_return_url(),
        )

        url = session.get("url")
        if not url:
            return _json_error("Stripe portal URL not returned", 500)

        return jsonify({"url": url}), 200

    except RuntimeError as e:
        current_app.logger.error("Portal config error: %s", e)
        return _json_error(
            "Portal configuration error",
            500,
            detail=str(e),
        )

    except Exception as e:
        current_app.logger.exception(
            "Stripe portal session creation failed"
        )
        return _json_error(
            "Failed to create portal session",
            500,
            detail=str(e),
        )


if __name__ == "__main__":
    assert portal_bp.name == "portal"
    print("billing/customer_portal.py deployment-ready")

# File: billing/invoices.py
# Purpose: Stripe invoice retrieval (list + detail + upcoming) + PDF/hosted URLs (FULL production)
# Date: 2026-01-26
# Status: Production-grade (safe env validation, company_id->customer mapping, deterministic output)

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, Response, jsonify, request

from billing.customers import get_company_customer, get_or_create_company_customer


invoices_bp = Blueprint("billing_invoices", __name__, url_prefix="/billing")


# -----------------------------
# ENV / STRIPE
# -----------------------------
def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name, default)
    if v is None:
        return None
    v = v.strip()
    return v if v else None


def _validate_secret_key(key: str) -> None:
    if not key:
        raise RuntimeError("Missing STRIPE_SECRET_KEY")
    if key in {"sk_live", "sk_test"}:
        raise RuntimeError("Invalid STRIPE_SECRET_KEY (truncated)")
    if not (key.startswith("sk_live_") or key.startswith("sk_test_")):
        raise RuntimeError("Invalid STRIPE_SECRET_KEY format (must start with sk_live_ or sk_test_)")
    if len(key) < 20:
        raise RuntimeError("Invalid STRIPE_SECRET_KEY (too short)")


def _stripe():
    import stripe  # type: ignore

    key = (_env("STRIPE_SECRET_KEY") or "")
    _validate_secret_key(key)
    stripe.api_key = key
    return stripe


# -----------------------------
# INPUT RESOLUTION
# -----------------------------
def _extract_company_id() -> Optional[int]:
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
      - Prefer company_id -> persisted mapping (stable)
      - Fallback to explicit customer_id (legacy/admin/support use)
    """
    company_id = _extract_company_id()
    if company_id is not None:
        rec = get_company_customer(company_id)
        scid = (rec.get("stripe_customer_id") if rec else "") or ""
        scid = scid.strip()
        if scid.startswith("cus_"):
            return scid

        rec2 = get_or_create_company_customer(company_id=company_id)
        scid2 = (rec2.get("stripe_customer_id") or "").strip()
        return scid2 if scid2.startswith("cus_") else None

    cid = _extract_customer_id()
    if cid and cid.startswith("cus_"):
        return cid
    return None


def _json_error(msg: str, status: int = 400, **extra: Any) -> Tuple[Response, int]:
    payload: Dict[str, Any] = {"error": msg}
    payload.update(extra)
    return jsonify(payload), status


# -----------------------------
# NORMALIZATION
# -----------------------------
def _money(amount: Optional[int], currency: Optional[str]) -> Dict[str, Any]:
    return {
        "amount": int(amount or 0),
        "currency": (currency or "").lower() or None,
    }


def _invoice_compact(inv: Dict[str, Any]) -> Dict[str, Any]:
    # Stripe fields are stable; guard everything anyway.
    invoice_id = str(inv.get("id") or "").strip() or None
    status = str(inv.get("status") or "").strip().lower() or None
    customer = str(inv.get("customer") or "").strip() or None
    subscription = inv.get("subscription")
    subscription_id = str(subscription).strip() if subscription else None

    # Best URLs for user-facing invoice
    hosted = inv.get("hosted_invoice_url")
    pdf = inv.get("invoice_pdf")

    return {
        "id": invoice_id,
        "status": status,
        "customer_id": customer,
        "subscription_id": subscription_id,
        "number": inv.get("number"),
        "created": inv.get("created"),
        "period_start": inv.get("period_start"),
        "period_end": inv.get("period_end"),
        "due_date": inv.get("due_date"),
        "paid": bool(inv.get("paid", False)),
        "attempted": bool(inv.get("attempted", False)),
        "attempt_count": int(inv.get("attempt_count") or 0),
        "total": _money(inv.get("total"), inv.get("currency")),
        "amount_due": _money(inv.get("amount_due"), inv.get("currency")),
        "amount_paid": _money(inv.get("amount_paid"), inv.get("currency")),
        "amount_remaining": _money(inv.get("amount_remaining"), inv.get("currency")),
        "hosted_invoice_url": hosted if isinstance(hosted, str) and hosted else None,
        "invoice_pdf": pdf if isinstance(pdf, str) and pdf else None,
        "collection_method": inv.get("collection_method"),
        "billing_reason": inv.get("billing_reason"),
    }


def _as_dict(obj: Any) -> Dict[str, Any]:
    # Stripe SDK returns StripeObject; normalize
    if isinstance(obj, dict):
        return obj
    try:
        return dict(obj)  # type: ignore[arg-type]
    except Exception:
        try:
            return obj.to_dict_recursive()  # type: ignore[no-any-return]
        except Exception:
            return {}


# -----------------------------
# ROUTES
# -----------------------------
@invoices_bp.get("/invoices/health")
def invoices_health() -> Tuple[Response, int]:
    try:
        _stripe()
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500


@invoices_bp.get("/invoices")
def list_invoices() -> Tuple[Response, int]:
    """
    GET /billing/invoices?limit=10
    Headers (preferred): X-Company-Id
    Fallback: X-Customer-Id
    """
    stripe_customer_id = _resolve_stripe_customer_id()
    if not stripe_customer_id:
        return _json_error(
            "missing_customer",
            400,
            hint="Provide X-Company-Id (preferred) or X-Customer-Id.",
        )

    try:
        limit_raw = request.args.get("limit", "10")
        try:
            limit = int(str(limit_raw).strip())
        except Exception:
            limit = 10
        limit = max(1, min(limit, 50))

        stripe = _stripe()
        res = stripe.Invoice.list(customer=stripe_customer_id, limit=limit)
        data = res.get("data") or []
        out: List[Dict[str, Any]] = [_invoice_compact(_as_dict(i)) for i in data]

        return jsonify({"customer_id": stripe_customer_id, "invoices": out}), 200
    except Exception as e:
        return _json_error("stripe_error", 502, detail=str(e))


@invoices_bp.get("/invoices/upcoming")
def upcoming_invoice() -> Tuple[Response, int]:
    """
    GET /billing/invoices/upcoming
    Returns upcoming invoice if exists; else 404 with deterministic payload.
    """
    stripe_customer_id = _resolve_stripe_customer_id()
    if not stripe_customer_id:
        return _json_error(
            "missing_customer",
            400,
            hint="Provide X-Company-Id (preferred) or X-Customer-Id.",
        )

    try:
        stripe = _stripe()
        inv = stripe.Invoice.upcoming(customer=stripe_customer_id)
        inv_d = _as_dict(inv)
        return jsonify({"customer_id": stripe_customer_id, "invoice": _invoice_compact(inv_d)}), 200
    except Exception as e:
        msg = str(e)
        # Stripe raises InvalidRequestError when no upcoming invoice exists.
        if "No upcoming invoices" in msg or "upcoming invoice" in msg.lower():
            return jsonify(
                {
                    "customer_id": stripe_customer_id,
                    "invoice": None,
                    "reason": "no_upcoming_invoice",
                }
            ), 404
        return _json_error("stripe_error", 502, detail=msg)


@invoices_bp.get("/invoices/<invoice_id>")
def get_invoice(invoice_id: str) -> Tuple[Response, int]:
    """
    GET /billing/invoices/<invoice_id>
    """
    iid = (invoice_id or "").strip()
    if not iid or not iid.startswith("in_"):
        return _json_error("invalid_invoice_id", 400)

    try:
        stripe = _stripe()
        inv = stripe.Invoice.retrieve(iid)
        inv_d = _as_dict(inv)
        return jsonify({"invoice": _invoice_compact(inv_d)}), 200
    except Exception as e:
        msg = str(e)
        if "No such invoice" in msg or "resource_missing" in msg.lower():
            return _json_error("not_found", 404)
        return _json_error("stripe_error", 502, detail=msg)


# Export expected symbol if you register it elsewhere
billing_invoices_bp = invoices_bp


if __name__ == "__main__":
    assert invoices_bp.name == "billing_invoices"
    print("billing/invoices.py FULL PRODUCTION OK")

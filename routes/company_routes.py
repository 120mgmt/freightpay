# File: routes/company_routes.py
# Purpose: Company onboarding (create tenant + optional Stripe customer binding)
# Status: Production-ready (root-based imports, Postgres-safe, Stripe-safe)
# Date: 2026-01-24

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from db import db
from models.company import Company
from services.coa import seed_default_coa

company_bp = Blueprint("company", __name__, url_prefix="/companies")


# -------------------------
# Helpers
# -------------------------
def _json_error(msg: str, code: int = 400, **extra: Any):
    payload: Dict[str, Any] = {"error": msg}
    payload.update(extra)
    return jsonify(payload), code


def _get_json() -> Dict[str, Any]:
    data = request.get_json(silent=True) or {}
    return data if isinstance(data, dict) else {}


def _slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def _truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return str(v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _stripe_client():
    try:
        import stripe  # type: ignore
    except Exception as e:
        raise RuntimeError(f"Stripe library not available: {e}") from e

    secret = (request.environ.get("STRIPE_SECRET_KEY") or "").strip()  # rarely set
    if not secret:
        import os

        secret = (os.getenv("STRIPE_SECRET_KEY") or "").strip()

    if not secret:
        raise RuntimeError("Missing STRIPE_SECRET_KEY env var")
    if secret in {"sk_live", "sk_test"} or not (secret.startswith("sk_live_") or secret.startswith("sk_test_")):
        raise RuntimeError("Invalid STRIPE_SECRET_KEY format (must start with sk_live_ or sk_test_)")

    stripe.api_key = secret
    return stripe


def _create_stripe_customer(*, name: str, slug: str, company_id: int, email: Optional[str]) -> str:
    stripe = _stripe_client()
    cust = stripe.Customer.create(
        name=name,
        email=email or None,
        metadata={
            "company_id": str(company_id),
            "company_slug": slug,
            "product": "ledgerhaul",
        },
    )
    cid = cust.get("id") if isinstance(cust, dict) else None
    if not isinstance(cid, str) or not cid.strip():
        raise RuntimeError("Stripe did not return a customer id")
    return cid.strip()


# -------------------------
# Routes
# -------------------------
@company_bp.get("/health")
def company_health():
    return jsonify({"status": "ok"}), 200


@company_bp.post("")
def create_company():
    """
    POST /companies
    Body:
      {
        "name": "Acme Logistics",
        "slug": "acme-logistics"   (optional)
        "create_stripe_customer": true (optional; default true)
        "billing_email": "owner@acme.com" (optional)
      }

    Returns: Company JSON (includes stripe_customer_id when created)
    """
    data = _get_json()

    name = (data.get("name") or "").strip()
    if not name:
        return _json_error("name required", 400)

    slug_in = (data.get("slug") or "").strip()
    slug = _slugify(slug_in or name)
    if not slug:
        return _json_error("Invalid slug/name", 400)

    create_stripe = _truthy(data.get("create_stripe_customer", True))
    billing_email = (data.get("billing_email") or "").strip() or None

    # Create tenant
    company = Company(name=name, slug=slug)

    try:
        db.session.add(company)
        db.session.flush()  # ensure company.id exists before seeding
        seed_default_coa(db.session, company_id=company.id)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        # slug unique index
        return _json_error("Company slug already exists", 409, slug=slug)
    except Exception as e:
        db.session.rollback()
        return _json_error("Failed to create company", 500, detail=str(e))

    # Optional Stripe binding (sellable SaaS: tenant ↔ Stripe customer)
    if create_stripe:
        try:
            stripe_customer_id = _create_stripe_customer(
                name=company.name,
                slug=company.slug,
                company_id=int(company.id),
                email=billing_email,
            )
            company.stripe_customer_id = stripe_customer_id
            db.session.commit()
        except Exception as e:
            # Company exists even if Stripe fails; return actionable detail.
            db.session.rollback()
            return _json_error(
                "Company created but Stripe customer creation failed",
                502,
                company=company.to_dict(),
                detail=str(e),
            )

    return jsonify(company.to_dict()), 201


@company_bp.get("/<int:company_id>")
def get_company(company_id: int):
    company = Company.query.get(company_id)
    if not company:
        return _json_error("Company not found", 404)
    return jsonify(company.to_dict()), 200


@company_bp.get("")
def list_companies():
    try:
        limit = int((request.args.get("limit") or "25").strip())
        limit = max(1, min(limit, 200))
    except Exception:
        limit = 25

    rows = Company.query.order_by(Company.id.desc()).limit(limit).all()
    return jsonify({"companies": [c.to_dict() for c in rows]}), 200


__all__ = ["company_bp"]


if __name__ == "__main__":
    assert company_bp.name == "company"
    print("routes/company_routes.py OK")

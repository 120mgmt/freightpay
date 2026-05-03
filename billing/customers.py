# File: billing/customers.py
# Purpose: Stripe Customer ownership
# Purpose: create + persist + retrieve
# Purpose: closes billing lifecycle gap
# Status: Production-hardened
# Status: Render-safe, persistent DB via Postgres
# Status: idempotent customer creation
# Date: 2026-01-24

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from db import db

customer_bp = Blueprint(
    "billing_customers",
    __name__,
    url_prefix="/billing/customers",
)


def _json_error(
    message: str,
    status: int = 400,
    **extra: Any,
) -> Tuple[Response, int]:
    payload: Dict[str, Any] = {"error": message}
    payload.update(extra)
    return jsonify(payload), status


def _now() -> int:
    return int(time.time())


def _init_db() -> None:
    """
    Persist customer mapping in the PRIMARY DATABASE (Postgres on Render),
    not /tmp SQLite (which is ephemeral and causes customer_not_found
    after restarts).
    """
    ddl = """
    CREATE TABLE IF NOT EXISTS company_customers (
        company_id INTEGER PRIMARY KEY,
        stripe_customer_id TEXT NOT NULL,
        email TEXT,
        name TEXT,
        created_at BIGINT NOT NULL,
        updated_at BIGINT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_company_customers_stripe_customer_id
        ON company_customers (stripe_customer_id);
    """
    try:
        with db.engine.begin() as conn:
            for stmt in [s.strip() for s in ddl.split(";") if s.strip()]:
                conn.execute(text(stmt))
    except Exception as e:
        current_app.logger.error("company_customers init failed: %s", e)


def _require_company_id() -> int:
    """
    Accepts company_id from:
      - X-Company-Id header
      - query param company_id
      - JSON body company_id

    NOTE: Allows company_id=0 because your environment already uses it.
    """
    cid = (
        request.headers.get("X-Company-Id")
        or request.args.get("company_id")
        or (request.get_json(silent=True) or {}).get("company_id")
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


def _validate_stripe_secret_key(secret: str) -> None:
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


def _stripe_client():
    try:
        import stripe  # type: ignore
    except Exception as e:
        raise RuntimeError(f"Stripe library not available: {e}") from e

    secret = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
    _validate_stripe_secret_key(secret)
    stripe.api_key = secret
    return stripe


def _ensure_initialized() -> None:
    try:
        _init_db()
    except Exception:
        pass


def get_company_customer(company_id: int) -> Optional[Dict[str, Any]]:
    _ensure_initialized()
    try:
        with db.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT
                        company_id,
                        stripe_customer_id,
                        email,
                        name,
                        created_at,
                        updated_at
                    FROM company_customers
                    WHERE company_id = :company_id
                    """
                ),
                {"company_id": company_id},
            ).mappings().fetchone()

        if not row:
            return None

        return {
            "company_id": int(row["company_id"]),
            "stripe_customer_id": str(row["stripe_customer_id"]),
            "email": row["email"],
            "name": row["name"],
            "created_at": int(row["created_at"]),
            "updated_at": int(row["updated_at"]),
        }
    except SQLAlchemyError as e:
        current_app.logger.error("DB error get_company_customer: %s", e)
        return None


def upsert_company_customer(
    *,
    company_id: int,
    stripe_customer_id: str,
    email: Optional[str],
    name: Optional[str],
) -> None:
    _ensure_initialized()

    if stripe_customer_id is None or not str(stripe_customer_id).strip():
        raise ValueError("stripe_customer_id is required")

    scid = str(stripe_customer_id).strip()
    if not scid.startswith("cus_"):
        raise ValueError(
            "stripe_customer_id must look like a Stripe customer id "
            "(cus_...)"
        )

    ts = _now()

    sql = """
    INSERT INTO company_customers (
        company_id,
        stripe_customer_id,
        email,
        name,
        created_at,
        updated_at
    )
    VALUES (
        :company_id,
        :stripe_customer_id,
        :email,
        :name,
        :created_at,
        :updated_at
    )
    ON CONFLICT (company_id) DO UPDATE SET
        stripe_customer_id = EXCLUDED.stripe_customer_id,
        email = EXCLUDED.email,
        name = EXCLUDED.name,
        updated_at = EXCLUDED.updated_at
    """

    with db.engine.begin() as conn:
        conn.execute(
            text(sql),
            {
                "company_id": company_id,
                "stripe_customer_id": scid,
                "email": email,
                "name": name,
                "created_at": ts,
                "updated_at": ts,
            },
        )


def _find_existing_stripe_customer_for_company(
    stripe,
    company_id: int,
) -> Optional[str]:
    """
    Fallback when DB mapping is missing:
    - Prefer Customer.search if available.
    - Otherwise list a small page and check metadata (best-effort).
    """
    cid = str(company_id)

    try:
        res = stripe.Customer.search(
            query=f"metadata['company_id']:'{cid}'",
            limit=1,
        )
        data = res.get("data") or []
        if data and (data[0].get("id") or "").startswith("cus_"):
            return data[0]["id"]
    except Exception:
        pass

    try:
        res = stripe.Customer.list(limit=100)
        for customer in res.get("data") or []:
            md = customer.get("metadata") or {}
            if (
                str(md.get("company_id") or "") == cid
                and (customer.get("id") or "").startswith("cus_")
            ):
                return customer["id"]
    except Exception:
        pass

    return None


def get_or_create_company_customer(
    *,
    company_id: int,
    email: Optional[str] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    existing = get_company_customer(company_id)
    if existing:
        return existing

    stripe = _stripe_client()

    recovered = _find_existing_stripe_customer_for_company(
        stripe,
        company_id,
    )
    if recovered:
        upsert_company_customer(
            company_id=company_id,
            stripe_customer_id=recovered,
            email=email,
            name=name,
        )
        rec = get_company_customer(company_id)
        if rec:
            return rec

    cust = stripe.Customer.create(
        email=email,
        name=name,
        metadata={
            "company_id": str(company_id),
            "app": "LedgerHaul",
        },
        idempotency_key=(
            f"ledgerhaul_customer_create_company_{company_id}"
        ),
    )

    stripe_customer_id = (cust.get("id") or "").strip()
    if not stripe_customer_id:
        raise RuntimeError("Stripe did not return a customer id")

    upsert_company_customer(
        company_id=company_id,
        stripe_customer_id=stripe_customer_id,
        email=email,
        name=name,
    )

    return get_company_customer(company_id) or {
        "company_id": company_id,
        "stripe_customer_id": stripe_customer_id,
        "email": email,
        "name": name,
        "created_at": _now(),
        "updated_at": _now(),
    }


@customer_bp.get("/health")
def customers_health() -> Tuple[Response, int]:
    try:
        _ensure_initialized()
        with db.engine.begin() as conn:
            conn.execute(text("SELECT 1"))
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500


@customer_bp.get("/me")
def customers_me() -> Tuple[Response, int]:
    try:
        company_id = _require_company_id()
        rec = get_company_customer(company_id)
        if not rec:
            return _json_error(
                "customer_not_found",
                404,
                company_id=company_id,
            )
        return jsonify(rec), 200
    except Exception as e:
        return _json_error("invalid_request", 400, detail=str(e))


@customer_bp.post("/create")
def customers_create() -> Tuple[Response, int]:
    try:
        company_id = _require_company_id()
        data = request.get_json(silent=True) or {}

        email = (
            data.get("email")
            or request.args.get("email")
            or ""
        ).strip() or None
        name = (
            data.get("name")
            or request.args.get("name")
            or ""
        ).strip() or None

        rec = get_or_create_company_customer(
            company_id=company_id,
            email=email,
            name=name,
        )
        return jsonify(rec), 201
    except RuntimeError as e:
        current_app.logger.error("Stripe customer create failed: %s", e)
        return _json_error("stripe_error", 500, detail=str(e))
    except Exception as e:
        return _json_error("invalid_request", 400, detail=str(e))


@customer_bp.get("/create-link")
def customers_create_link() -> Tuple[Response, int]:
    """
    GET create (browser-friendly)

    Example:
      /billing/customers/create-link
      ?company_id=0
      &email=you@domain.com
      &name=LedgerHaul%20User
    """
    try:
        company_id = _require_company_id()
        email = (request.args.get("email") or "").strip() or None
        name = (request.args.get("name") or "").strip() or None

        rec = get_or_create_company_customer(
            company_id=company_id,
            email=email,
            name=name,
        )
        return jsonify(rec), 200
    except RuntimeError as e:
        current_app.logger.error("Stripe customer create failed: %s", e)
        return _json_error("stripe_error", 500, detail=str(e))
    except Exception as e:
        return _json_error("invalid_request", 400, detail=str(e))


__all__ = [
    "customer_bp",
    "get_company_customer",
    "get_or_create_company_customer",
]


if __name__ == "__main__":
    assert customer_bp.name == "billing_customers"
    print("billing/customers.py OK")

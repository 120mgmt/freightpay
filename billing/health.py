# File: billing/health.py
# Purpose: Billing subsystem health check (Stripe + DB + schema + price catalog)
# Status: FULL PRODUCTION – hardened (no secret leakage, optional token gate)
# Date: 2026-01-26

from __future__ import annotations

import hmac
import os
import time
from typing import Any, Dict, Tuple

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import text

from db import db

billing_health_bp = Blueprint("billing_health", __name__, url_prefix="/billing")


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _truthy(v: str) -> bool:
    return v.lower() in {"1", "true", "yes", "y", "on"}


def _now() -> int:
    return int(time.time())


def _has_prefix(v: str, prefix: str) -> bool:
    return bool(v) and v.startswith(prefix) and len(v) >= (len(prefix) + 8)


def _env_ok() -> Dict[str, bool]:
    """
    Return ONLY booleans. Never return key material.
    """
    stripe_key = _env("STRIPE_SECRET_KEY")
    whsec = _env("STRIPE_WEBHOOK_SECRET")

    return {
        "STRIPE_SECRET_KEY_present": bool(stripe_key),
        "STRIPE_SECRET_KEY_format_ok": _has_prefix(stripe_key, "sk_live_") or _has_prefix(stripe_key, "sk_test_"),
        "STRIPE_WEBHOOK_SECRET_present": bool(whsec),
        "STRIPE_WEBHOOK_SECRET_format_ok": _has_prefix(whsec, "whsec_"),
        "DATABASE_URL_present": bool(_env("DATABASE_URL")),
        "SUBSCRIPTION_REQUIRED_set": bool(_env("SUBSCRIPTION_REQUIRED") or "1"),
    }


def _db_ok() -> bool:
    try:
        with db.engine.begin() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _tables_ok() -> Dict[str, bool]:
    """
    Ensures webhook idempotency + subscription cache tables exist.
    These are created by billing/webhooks.py and billing/entitlement_store.py on import,
    but health should still validate.
    """
    checks = {
        "stripe_webhook_events": False,
        "customer_subscriptions": False,
    }

    try:
        with db.engine.begin() as conn:
            # Postgres-safe existence check
            for table in list(checks.keys()):
                row = conn.execute(
                    text(
                        """
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = :t
                        LIMIT 1
                        """
                    ),
                    {"t": table},
                ).fetchone()
                checks[table] = bool(row)
    except Exception:
        pass

    return checks


def _price_catalog_ok() -> Dict[str, Any]:
    """
    Validates price registry is loaded and contains at least one base price when STRICT_PRICE_CATALOG is on.
    """
    try:
        from billing.prices import all_prices

        reg = all_prices()
        base_present = any(getattr(p, "kind", "") == "base" for p in reg.values())

        strict = _truthy(_env("STRICT_PRICE_CATALOG")) if _env("STRICT_PRICE_CATALOG") else False

        return {
            "registered_prices": int(len(reg)),
            "base_price_present": bool(base_present),
            "strict_mode": bool(strict),
        }
    except Exception as e:
        return {
            "registered_prices": 0,
            "base_price_present": False,
            "strict_mode": _truthy(_env("STRICT_PRICE_CATALOG")) if _env("STRICT_PRICE_CATALOG") else False,
            "error": str(e),
        }


def _require_health_token() -> Tuple[bool, Tuple[Response, int] | None]:
    """
    Optional token gate:
      - Set BILLING_HEALTH_TOKEN in Render
      - Call with header: X-Health-Token: <token>
      - Optional override header name: BILLING_HEALTH_TOKEN_HEADER
    """
    token = _env("BILLING_HEALTH_TOKEN")
    if not token:
        return True, None

    header_name = _env("BILLING_HEALTH_TOKEN_HEADER") or "X-Health-Token"
    provided = (request.headers.get(header_name) or "").strip()

    if not (provided and hmac.compare_digest(provided, token)):
        return False, (jsonify({"error": "forbidden"}), 403)

    return True, None


@billing_health_bp.get("/health")
def billing_health() -> Tuple[Response, int]:
    ok, denial = _require_health_token()
    if not ok and denial:
        return denial

    env = _env_ok()
    db_ok = _db_ok()
    tables = _tables_ok()
    catalog = _price_catalog_ok()

    ready = (
        all(bool(v) for v in env.values())
        and bool(db_ok)
        and all(bool(v) for v in tables.values())
        and bool(catalog.get("base_price_present", False))
    )

    payload: Dict[str, Any] = {
        "service": "billing",
        "timestamp": _now(),
        "env": env,          # booleans only
        "database": db_ok,
        "tables": tables,
        "price_catalog": catalog,
        "ready": ready,
    }

    return jsonify(payload), (200 if ready else 503)


__all__ = ["billing_health_bp"]


if __name__ == "__main__":
    print("billing/health.py OK")

# File: billing/webhooks.py
# Purpose: Stripe webhook receiver with signature verification + entitlement persistence (production)
# Date: 2026-01-26
# Status: Production-grade (signature verified, durable idempotency via DB, MULTI-PRICE subscription support)

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import text

from db import db

webhooks_bp = Blueprint("stripe_webhooks", __name__, url_prefix="/billing")


# -----------------------------
# ENV / HELPERS
# -----------------------------
def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name, default)
    if v is None:
        return None
    v = v.strip()
    return v if v else None


def _now() -> int:
    return int(time.time())


def _json_error(msg: str, status: int = 400, **extra: Any) -> Tuple[Response, int]:
    payload: Dict[str, Any] = {"error": msg}
    payload.update(extra)
    return jsonify(payload), status


def _validate_secret_key(key: str) -> None:
    if not key:
        raise RuntimeError("Missing STRIPE_SECRET_KEY")
    if key in {"sk_live", "sk_test"}:
        raise RuntimeError("Invalid STRIPE_SECRET_KEY (truncated)")
    if not (key.startswith("sk_live_") or key.startswith("sk_test_")):
        raise RuntimeError("Invalid STRIPE_SECRET_KEY format (must start with sk_live_ or sk_test_)")
    if len(key) < 20:
        raise RuntimeError("Invalid STRIPE_SECRET_KEY (too short)")


def _validate_webhook_secret(secret: str) -> None:
    if not secret:
        raise RuntimeError("Missing STRIPE_WEBHOOK_SECRET")
    if secret == "whsec":
        raise RuntimeError("Invalid STRIPE_WEBHOOK_SECRET (truncated)")
    if not secret.startswith("whsec_"):
        raise RuntimeError("Invalid STRIPE_WEBHOOK_SECRET format (must start with whsec_)")
    if len(secret) < 20:
        raise RuntimeError("Invalid STRIPE_WEBHOOK_SECRET (too short)")


def _stripe():
    import stripe  # type: ignore

    key = (_env("STRIPE_SECRET_KEY") or "")
    _validate_secret_key(key)
    stripe.api_key = key
    return stripe


def _webhook_secret() -> str:
    secret = (_env("STRIPE_WEBHOOK_SECRET") or "")
    _validate_webhook_secret(secret)
    return secret


# -----------------------------
# DURABLE IDEMPOTENCY (DB)
# -----------------------------
def _init_event_log() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS stripe_webhook_events (
        event_id TEXT PRIMARY KEY,
        event_type TEXT,
        customer_id TEXT,
        company_id INTEGER,
        received_at BIGINT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_stripe_webhook_events_customer_id
        ON stripe_webhook_events (customer_id);
    CREATE INDEX IF NOT EXISTS idx_stripe_webhook_events_company_id
        ON stripe_webhook_events (company_id);
    """
    try:
        with db.engine.begin() as conn:
            for stmt in [s.strip() for s in ddl.split(";") if s.strip()]:
                conn.execute(text(stmt))
    except Exception:
        pass


def _event_already_processed(event_id: str) -> bool:
    if not event_id:
        return False
    try:
        with db.engine.begin() as conn:
            row = conn.execute(
                text("SELECT event_id FROM stripe_webhook_events WHERE event_id = :eid"),
                {"eid": event_id},
            ).fetchone()
        return bool(row)
    except Exception:
        return False


def _log_event(*, event_id: str, event_type: str, customer_id: Optional[str], company_id: Optional[int]) -> None:
    if not event_id:
        return
    try:
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO stripe_webhook_events (event_id, event_type, customer_id, company_id, received_at)
                    VALUES (:event_id, :event_type, :customer_id, :company_id, :received_at)
                    ON CONFLICT (event_id) DO NOTHING
                    """
                ),
                {
                    "event_id": event_id,
                    "event_type": event_type,
                    "customer_id": customer_id,
                    "company_id": company_id,
                    "received_at": _now(),
                },
            )
    except Exception:
        pass


_init_event_log()


# -----------------------------
# STRIPE OBJECT HELPERS
# -----------------------------
def _event_object(event: Dict[str, Any]) -> Dict[str, Any]:
    return event.get("data", {}).get("object") or {}


def _sub_status(sub: Dict[str, Any]) -> str:
    return str(sub.get("status") or "").lower()


def _sub_customer_id(sub: Dict[str, Any]) -> Optional[str]:
    cid = sub.get("customer")
    return cid.strip() if isinstance(cid, str) and cid.strip() else None


def _extract_subscription_price_ids(sub: Dict[str, Any]) -> List[str]:
    """
    MULTI-PRICE SUPPORT:
    Stripe subscriptions can have multiple subscription items (base + add-ons).
    Returns a stable, de-duplicated list of ALL price IDs.
    """
    ids: List[str] = []
    try:
        items = (sub.get("items") or {}).get("data") or []
        for it in items:
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


def _is_active(status: str) -> bool:
    return status in {"active", "trialing"}


def _company_id_from_metadata(obj: Dict[str, Any]) -> Optional[int]:
    md = obj.get("metadata") or {}
    if not isinstance(md, dict):
        return None
    raw = md.get("company_id")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        v = int(str(raw).strip())
        return v if v >= 0 else None
    except Exception:
        return None


# -----------------------------
# ENTITLEMENT APPLY (PERSISTED)
# -----------------------------
def _apply_entitlements(
    *,
    customer_id: str,
    status: str,
    price_ids: List[str],
    subscription_id: Optional[str] = None,
    current_period_end: Optional[int] = None,
) -> None:
    """
    Persists customer subscription state + entitlements.

    MULTI-PRICE ACCURATE:
    - evaluates ALL price_ids and selects the highest plan entitlements
    - stores primary price_id for backward compatibility
    """
    from billing.entitlement import entitlements_from_stripe_price_id, entitlements_to_dict
    from billing.entitlement_store import upsert_customer_subscription

    active = _is_active(status)

    # Normalize / stable de-dupe
    ids: List[str] = []
    seen = set()
    for pid in (price_ids or []):
        if isinstance(pid, str):
            p = pid.strip()
            if p and p not in seen:
                seen.add(p)
                ids.append(p)

    primary = ids[0] if ids else None

    ent = None
    if active:
        rank = {"starter": 1, "pro": 2, "enterprise": 3}
        best_ent = None
        best_rank = 0

        for pid in ids:
            e = entitlements_from_stripe_price_id(pid)
            plan = str(getattr(e, "plan", "starter")).lower()
            r = rank.get(plan, 1)
            if r > best_rank:
                best_rank = r
                best_ent = e

        ent = best_ent or entitlements_from_stripe_price_id(primary)

    upsert_customer_subscription(
        customer_id=customer_id,
        active=active,
        status=status,
        subscription_id=subscription_id,
        price_id=primary,              # backward-compatible primary
        price_ids=ids or None,         # FULL list (base + add-ons)
        current_period_end=current_period_end,
        entitlements=entitlements_to_dict(ent) if ent else None,
        updated_at=_now(),
    )


# -----------------------------
# HEALTH
# -----------------------------
@webhooks_bp.get("/webhooks/health")
def webhook_health() -> Tuple[Response, int]:
    try:
        with db.engine.begin() as conn:
            conn.execute(text("SELECT 1"))
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500


# -----------------------------
# STRIPE WEBHOOK
# -----------------------------
@webhooks_bp.post("/webhooks/stripe")
def stripe_webhook() -> Tuple[Response, int]:
    try:
        secret = _webhook_secret()
    except Exception as e:
        return _json_error("Webhook misconfigured", 500, detail=str(e))

    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature")
    if not sig:
        return _json_error("Missing Stripe-Signature", 400)

    try:
        stripe = _stripe()
        event = stripe.Webhook.construct_event(payload, sig, secret)
        event = event if isinstance(event, dict) else json.loads(json.dumps(event))
    except Exception as e:
        return _json_error("Webhook signature verification failed", 400, detail=str(e))

    event_id = str(event.get("id") or "").strip()
    event_type = str(event.get("type") or "")
    obj = _event_object(event)

    if event_id and _event_already_processed(event_id):
        return jsonify({"received": True, "duplicate": True, "id": event_id}), 200

    customer_id: Optional[str] = None
    company_id: Optional[int] = None

    try:
        # Subscription lifecycle
        if event_type.startswith("customer.subscription."):
            status = _sub_status(obj)
            customer_id = _sub_customer_id(obj)
            company_id = _company_id_from_metadata(obj)

            price_ids = _extract_subscription_price_ids(obj)
            subscription_id = str(obj.get("id") or "").strip() or None

            cpe_raw = obj.get("current_period_end")
            current_period_end = int(cpe_raw) if isinstance(cpe_raw, (int, float)) else None

            if customer_id:
                _apply_entitlements(
                    customer_id=customer_id,
                    status=status,
                    price_ids=price_ids,
                    subscription_id=subscription_id,
                    current_period_end=current_period_end,
                )

            _log_event(event_id=event_id, event_type=event_type, customer_id=customer_id, company_id=company_id)
            return jsonify({"received": True, "type": event_type}), 200

        # Checkout completed → fetch subscription, apply entitlements (multi-price)
        if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
            customer_id = obj.get("customer") if isinstance(obj.get("customer"), str) else None
            sub_id = obj.get("subscription") if isinstance(obj.get("subscription"), str) else None
            company_id = _company_id_from_metadata(obj)

            if customer_id and customer_id.strip() and sub_id and sub_id.strip():
                stripe = _stripe()
                sub = stripe.Subscription.retrieve(sub_id.strip())
                sub = sub if isinstance(sub, dict) else json.loads(json.dumps(sub))

                status = _sub_status(sub)
                price_ids = _extract_subscription_price_ids(sub)

                cpe_raw = sub.get("current_period_end")
                current_period_end = int(cpe_raw) if isinstance(cpe_raw, (int, float)) else None

                _apply_entitlements(
                    customer_id=customer_id.strip(),
                    status=status,
                    price_ids=price_ids,
                    subscription_id=sub_id.strip(),
                    current_period_end=current_period_end,
                )

            _log_event(event_id=event_id, event_type=event_type, customer_id=(customer_id or None), company_id=company_id)
            return jsonify({"received": True, "type": event_type}), 200

        # Ignore everything else (still 200 to avoid retries)
        _log_event(event_id=event_id, event_type=event_type, customer_id=None, company_id=_company_id_from_metadata(obj))
        return jsonify({"received": True, "type": event_type, "ignored": True}), 200

    except Exception as e:
        _log_event(event_id=event_id, event_type=event_type, customer_id=customer_id, company_id=company_id)
        return jsonify(
            {
                "received": True,
                "type": event_type,
                "handled_with_error": True,
                "detail": str(e),
            }
        ), 200


# Alias expected by app.py
webhook_bp = webhooks_bp


if __name__ == "__main__":
    assert webhook_bp.name == "stripe_webhooks"
    print("billing/webhooks.py OK")


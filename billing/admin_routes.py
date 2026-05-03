# File: billing/admin_routes.py
# Purpose: Admin-only billing operations (safe reads + controlled actions)
# Status: FULL PRODUCTION – hardened, permission-gated
# Date: 2026-01-26

from __future__ import annotations

from typing import Dict, List

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import text

from db import db

admin_bp = Blueprint("billing_admin", __name__, url_prefix="/billing/admin")


def _is_admin(user) -> bool:
    return bool(getattr(user, "is_admin", False) or getattr(user, "role", "") == "admin")


@admin_bp.before_request
@login_required
def _guard():
    if not _is_admin(current_user):
        return jsonify({"error": "forbidden"}), 403


@admin_bp.get("/subscriptions")
def list_subscriptions() -> tuple[Dict, int]:
    """
    Read-only view of subscription state written by webhooks.
    """
    with db.engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT customer_id, active, status, subscription_id,
                       price_id, price_ids_json, updated_at
                FROM customer_subscriptions
                ORDER BY updated_at DESC
                LIMIT 500
                """
            )
        ).mappings().all()

    return jsonify({"subscriptions": list(rows)}), 200


@admin_bp.get("/webhook-events")
def list_webhook_events() -> tuple[Dict, int]:
    """
    Inspect Stripe webhook ingestion (idempotency verification).
    """
    limit = min(int(request.args.get("limit", 200)), 1000)

    with db.engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT event_id, event_type, customer_id, company_id, received_at
                FROM stripe_webhook_events
                ORDER BY received_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()

    return jsonify({"events": list(rows)}), 200


@admin_bp.post("/revoke-subscription")
def revoke_subscription() -> tuple[Dict, int]:
    """
    Emergency kill-switch (rare).
    Does NOT talk to Stripe — only disables local access.
    """
    data = request.get_json(force=True) or {}
    customer_id = (data.get("customer_id") or "").strip()

    if not customer_id:
        return jsonify({"error": "customer_id_required"}), 400

    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE customer_subscriptions
                SET active = false, status = 'revoked'
                WHERE customer_id = :cid
                """
            ),
            {"cid": customer_id},
        )

    return jsonify({"status": "revoked", "customer_id": customer_id}), 200

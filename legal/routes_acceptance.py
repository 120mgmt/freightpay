# freightpay/legal/routes_acceptance.py
# Purpose: Capture and enforce legal acceptance (Terms / Privacy / Refund)
# Status: Full deployment – production v5
# Date: 2026-01-01

from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy.orm import Session

from utils.database import get_db
from utils.auth import require_auth
from models import User
from legal.service import (
    has_current_legal_acceptance,
    record_legal_acceptance,
)

legal_acceptance_bp = Blueprint(
    "legal_acceptance",
    __name__,
    url_prefix="/legal/acceptance",
)


@legal_acceptance_bp.post("")
@require_auth
def accept_legal(user: User):
    db: Session = get_db()

    # If already accepted current versions, no-op
    if has_current_legal_acceptance(db, user):
        return jsonify({"status": "already_accepted"}), 200

    ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
    user_agent = request.headers.get("User-Agent")

    record_legal_acceptance(
        session=db,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return jsonify({"status": "accepted"}), 201


@legal_acceptance_bp.get("/status")
@require_auth
def legal_status(user: User):
    db: Session = get_db()

    return jsonify(
        {
            "accepted": has_current_legal_acceptance(db, user),
        }
    ), 200

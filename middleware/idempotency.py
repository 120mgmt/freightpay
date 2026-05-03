# File: middleware/idempotency.py
# Purpose: Global enterprise idempotency middleware for financial routes
# Status: Enterprise-hardened (request-level lock + replay safe)
# Date: 2026-02-26

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Callable

from flask import request, jsonify
from sqlalchemy import select, String, DateTime, Boolean, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import db


def _uuid():
    return uuid.uuid4()


class IdempotencyKey(db.Model):
    __tablename__ = "idempotency_keys"

    __table_args__ = (
        UniqueConstraint("key", name="uq_idempotency_key"),
        Index("ix_idempotency_processed", "processed"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )

    key: Mapped[str] = mapped_column(String(255), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(128), nullable=False)

    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    response_cache: Mapped[str | None] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)


def _hash_request() -> str:
    try:
        payload = request.get_json(silent=True) or {}
        raw = json.dumps(payload, sort_keys=True)
    except Exception:
        raw = ""
    return hashlib.sha256(raw.encode()).hexdigest()


def require_idempotency(handler: Callable):
    def wrapper(*args, **kwargs):

        key = request.headers.get("Idempotency-Key")
        if not key:
            return jsonify({"error": "missing_idempotency_key"}), 400

        request_hash = _hash_request()

        with db.session.begin():

            stmt = (
                select(IdempotencyKey)
                .where(IdempotencyKey.key == key)
                .with_for_update()
            )
            existing = db.session.execute(stmt).scalar_one_or_none()

            if existing:
                if existing.request_hash != request_hash:
                    return jsonify({"error": "idempotency_key_conflict"}), 409

                if existing.processed and existing.response_cache:
                    return jsonify(json.loads(existing.response_cache)), 200

            else:
                existing = IdempotencyKey(
                    key=key,
                    endpoint=request.path,
                    request_hash=request_hash,
                )
                db.session.add(existing)

        response = handler(*args, **kwargs)

        if isinstance(response, tuple):
            body, status = response
        else:
            body, status = response, 200

        if status < 400:
            with db.session.begin():
                existing.processed = True
                existing.processed_at = datetime.utcnow()
                existing.response_cache = json.dumps(body.json if hasattr(body, "json") else {})

        return response

    wrapper.__name__ = handler.__name__
    return wrapper

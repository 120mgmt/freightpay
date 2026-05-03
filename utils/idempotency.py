# File: utils/idempotency.py
# Purpose: Idempotency enforcement for billing + webhook safety
# Status: Production-ready
# Date: 2026-01-26

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint, Index

from db import db


class IdempotencyKey(db.Model):
    __tablename__ = "idempotency_keys"

    id = Column(Integer, primary_key=True)

    key = Column(String(128), nullable=False)
    scope = Column(String(64), nullable=False)  # billing | webhook | api
    request_hash = Column(String(128), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("key", "scope", name="uq_idempotency_key_scope"),
        Index("ix_idempotency_expires_at", "expires_at"),
    )


def reserve_idempotency_key(
    *,
    key: str,
    scope: str,
    ttl_seconds: int = 300,
    request_hash: str | None = None,
) -> bool:
    """
    Returns True if the key was successfully reserved.
    Returns False if the key already exists (duplicate request).
    """
    now = datetime.utcnow()
    expires_at = now + timedelta(seconds=ttl_seconds)

    existing = (
        IdempotencyKey.query
        .filter_by(key=key, scope=scope)
        .first()
    )

    if existing:
        return False

    rec = IdempotencyKey(
        key=key,
        scope=scope,
        request_hash=request_hash,
        expires_at=expires_at,
    )
    db.session.add(rec)
    db.session.commit()
    return True


def cleanup_expired_idempotency_keys() -> int:
    """
    Deletes expired keys. Safe to run via cron or background worker.
    """
    now = datetime.utcnow()
    q = IdempotencyKey.query.filter(IdempotencyKey.expires_at < now)
    count = q.count()
    q.delete(synchronize_session=False)
    db.session.commit()
    return count

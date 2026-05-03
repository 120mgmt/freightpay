# File: models/refresh_token.py
# Purpose: Refresh token persistence (JWT refresh token tracking / optional revocation)
# Status: Production-ready (Flask-SQLAlchemy, root imports, matches Integer PK models)
# Date: 2026-01-25

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.sql import func

from db import db


class RefreshToken(db.Model):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)

    # Match models/user.py: Integer PK
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # JWT unique id (jti) for revocation/rotation support
    jti = Column(String(64), nullable=False, unique=True, index=True)

    # Optional metadata
    token_type = Column(String(20), nullable=False, default="refresh")  # refresh
    revoked = Column(Boolean, nullable=False, default=False)

    # Store as ISO string or datetime depending on how you implement refresh endpoint later
    expires_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": int(self.id) if self.id is not None else None,
            "user_id": int(self.user_id) if self.user_id is not None else None,
            "jti": self.jti,
            "token_type": self.token_type,
            "revoked": bool(self.revoked),
            "expires_at": self.expires_at.isoformat() if isinstance(self.expires_at, datetime) else None,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else None,
        }


Index("ix_refresh_tokens_user_revoked", RefreshToken.user_id, RefreshToken.revoked)


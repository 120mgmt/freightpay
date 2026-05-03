# File: models/user.py
# Purpose: User model for LedgerHaul SaaS (auth, roles, legal enforcement)
# Status: Production-hardened
# Date: 2026-02-16

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash

from db import db


class User(db.Model):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Do NOT use index=True here (we define explicit indexes below)
    email = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)

    first_name = Column(String(100), nullable=False, default="")
    last_name = Column(String(100), nullable=False, default="")

    role = Column(String(50), nullable=False, default="admin")  # admin | manager | viewer
    is_active = Column(Boolean, nullable=False, default=True)

    # Email verification
    email_verified = Column(Boolean, nullable=False, default=False)

    # Legal acceptance
    accepted_tos = Column(Boolean, nullable=False, default=False)
    accepted_privacy = Column(Boolean, nullable=False, default=False)
    accepted_refund = Column(Boolean, nullable=False, default=False)
    legal_accepted_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", backref="users")

    # -------------------------
    # Auth helpers
    # -------------------------
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    # -------------------------
    # Legal helpers
    # -------------------------
    def mark_legal_accepted(
        self,
        *,
        tos: bool,
        privacy: bool,
        refund: bool | None = None,
    ) -> None:
        if tos:
            self.accepted_tos = True
        if privacy:
            self.accepted_privacy = True
        if refund:
            self.accepted_refund = True

        if (
            self.accepted_tos
            and self.accepted_privacy
            and self.accepted_refund
        ):
            self.legal_accepted_at = datetime.now(timezone.utc)

    # -------------------------
    # Serialization
    # -------------------------
    def to_dict(self) -> dict:
        return {
            "id": int(self.id) if self.id else None,
            "company_id": int(self.company_id) if self.company_id else None,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "role": self.role,
            "is_active": bool(self.is_active),
            "email_verified": bool(self.email_verified),
            "accepted_tos": bool(self.accepted_tos),
            "accepted_privacy": bool(self.accepted_privacy),
            "accepted_refund": bool(self.accepted_refund),
            "legal_accepted_at": self.legal_accepted_at.isoformat()
            if self.legal_accepted_at
            else None,
            "created_at": self.created_at.isoformat()
            if self.created_at
            else None,
            "updated_at": self.updated_at.isoformat()
            if self.updated_at
            else None,
        }


# Explicit indexes (safe, no duplicates)
Index("ix_users_company_email", User.company_id, User.email, unique=True)
Index("ix_users_email", User.email)
# File: utils/__init__.py
# Purpose: Central exports for utils (auth, legal guard, db helpers)
# Status: Production-ready
# Date: 2026-02-22

from __future__ import annotations

from .auth import (
    get_current_user,
    require_auth,
    login_user,
)

from .legal_guard import enforce_legal_acceptance

__all__ = [
    "get_current_user",
    "require_auth",
    "login_user",
    "enforce_legal_acceptance",
]

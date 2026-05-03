from __future__ import annotations

from typing import Callable, Iterable

from auth.jwt import decode_jwt  # uses your existing JWT decoder


class AuthorizationError(Exception):
    pass


def require_cpm_access(
    token: str,
    *,
    allowed_roles: Iterable[str],
) -> dict:
    """
    Enforces JWT + role for CPM operations.
    Returns auth context with company_id.
    """
    ctx = decode_jwt(token)

    if "company_id" not in ctx:
        raise AuthorizationError("company_id missing in JWT")

    if ctx.get("role") not in allowed_roles:
        raise AuthorizationError("insufficient role for CPM operation")

    return ctx

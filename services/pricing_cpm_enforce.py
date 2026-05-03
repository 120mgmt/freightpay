from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional, Sequence

from services.pricing_cpm_auth import require_cpm_access, AuthorizationError
from services.pricing_cpm_gate import evaluate_offer


def _d(val: Any) -> Decimal:
    return Decimal(str(val))


def enforce_cpm_with_jwt(
    *,
    token: str,
    company_id: int,
    trip_miles: Any,
    offered_rate_total: Optional[Any] = None,
    offered_rate_per_mile: Optional[Any] = None,
    allowed_roles: Sequence[str] = ("owner", "admin", "dispatcher"),
    overrides: Optional[dict] = None,
) -> dict:
    """
    Enforces:
      1) JWT + role + company_id scope
      2) CPM gate decision (reject blocks)
    Returns CPM decision payload on success.
    """
    ctx = require_cpm_access(token, allowed_roles=allowed_roles)

    jwt_company_id = int(ctx["company_id"])
    if int(company_id) != jwt_company_id:
        raise AuthorizationError("company_id mismatch between request and JWT")

    return evaluate_offer(
        int(company_id),
        trip_miles=_d(trip_miles),
        offered_rate_total=_d(offered_rate_total) if offered_rate_total is not None else None,
        offered_rate_per_mile=_d(offered_rate_per_mile) if offered_rate_per_mile is not None else None,
        overrides=overrides,
    )

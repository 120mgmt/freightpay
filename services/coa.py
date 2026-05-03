# services/coa.py
# Production COA service (migration-grade, trucking-standard)
# - Idempotent seeding per company
# - Company-scoped enforcement
# - System accounts locked from deletion (enforced in service layer where applicable)
# Date: 2026-03-08

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select

from db import db
from models.chart_of_accounts import Account, default_coa_rows


def _to_int_company_id(company_id: Any) -> int:
    s = str(company_id).strip()
    if not s:
        raise ValueError("company_id is required")
    try:
        v = int(s)
    except Exception:
        raise ValueError("company_id must be an integer")
    if v <= 0:
        raise ValueError("company_id must be > 0")
    return v


def _code_str(code: Any) -> str:
    c = str(code).strip()
    if not c:
        raise ValueError("account_code is required")
    return c


def _validate_code_range(code: str) -> None:
    try:
        v = int(code)
    except Exception:
        raise ValueError(f"Invalid account_code: {code}")
    if v < 1000 or v > 5999:
        raise ValueError(f"account_code out of allowed range (1000–5999): {code}")


def _safe_session(maybe_session: Any):
    return maybe_session if maybe_session is not None else db.session


def _to_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def _find_existing_by_code(session, company_id: int) -> Dict[str, Account]:
    stmt = select(Account).where(Account.company_id == company_id)
    rows = list(session.execute(stmt).scalars().all())
    out: Dict[str, Account] = {}
    for a in rows:
        try:
            out[_code_str(a.account_code)] = a
        except Exception:
            continue
    return out


def _apply_parent_links(
    session,
    company_id: int,
    created_or_existing: Dict[str, Account],
    template_rows: List[Dict[str, Any]],
) -> int:
    updates = 0
    for r in template_rows:
        code = _code_str(r.get("account_code"))
        parent_code = r.get("parent_code") or r.get("parent_account_code") or r.get("parent")
        if not parent_code:
            continue

        parent_code_s = _code_str(parent_code)
        child = created_or_existing.get(code)
        parent = created_or_existing.get(parent_code_s)
        if not child or not parent:
            continue

        if getattr(child, "parent_id", None) != parent.id:
            child.parent_id = parent.id
            updates += 1

    if updates:
        session.flush()

    return updates


def seed_default_coa(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    session = None
    company_id = None

    if args:
        first = args[0]
        if hasattr(first, "query") and hasattr(first, "add") and hasattr(first, "flush"):
            session = first
            if len(args) > 1:
                company_id = args[1]
        else:
            company_id = first

    if company_id is None and "company_id" in kwargs:
        kw_company_id = kwargs.get("company_id")
        if kw_company_id is not None and str(kw_company_id).strip():
            company_id = kw_company_id

    session = _safe_session(session)
    cid = _to_int_company_id(company_id)

    rows = default_coa_rows()
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("default_coa_rows() returned no rows")

    for r in rows:
        if not isinstance(r, dict):
            raise RuntimeError("default_coa_rows() must return list[dict]")
        code = _code_str(r.get("account_code"))
        _validate_code_range(code)

        name = str(r.get("name") or "").strip()
        if not name:
            raise ValueError(f"Missing name for account_code {code}")

        account_type = str(r.get("account_type") or "").strip().lower()
        if account_type not in {"asset", "liability", "equity", "revenue", "expense"}:
            raise ValueError(f"Invalid account_type for account_code {code}: {account_type}")

        normal_balance = str(r.get("normal_balance") or "").strip().lower()
        if normal_balance not in {"debit", "credit"}:
            raise ValueError(f"Invalid normal_balance for account_code {code}: {normal_balance}")

    existing = _find_existing_by_code(session, cid)

    seeded = 0
    for r in rows:
        code = _code_str(r.get("account_code"))
        if code in existing:
            acc = existing[code]

            if r.get("is_system") is True and getattr(acc, "is_system", False) is not True:
                acc.is_system = True

            if getattr(acc, "is_active", True) is not True:
                acc.is_active = True

            continue

        acc = Account(
            company_id=cid,
            account_code=code,
            name=str(r.get("name") or "").strip(),
            account_type=str(r.get("account_type") or "").strip().lower(),
            normal_balance=str(r.get("normal_balance") or "").strip().lower(),
            parent_id=None,
            is_active=_to_bool(r.get("is_active"), True),
            is_system=_to_bool(r.get("is_system"), True),
        )
        session.add(acc)
        seeded += 1

    session.flush()

    after = _find_existing_by_code(session, cid)

    updated = _apply_parent_links(session, cid, after, rows)

    return {
        "company_id": str(cid),
        "seeded": int(seeded),
        "updated": int(updated),
        "status": "ok",
    }


def seed_default_accounts(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    return seed_default_coa(*args, **kwargs)

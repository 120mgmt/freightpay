# services/coa.py
# COA SEEDING — idempotent default Chart of Accounts seeding per company

from __future__ import annotations

from typing import Iterable, Dict, Any

from sqlalchemy.orm import Session

from models.chart_of_accounts import Account, default_coa_rows


def seed_default_coa(db: Session, *, company_id) -> dict:
    """
    Seeds the default COA for a company (idempotent).
    - Creates only missing account_code rows for that company.
    - Marks seeded rows as system accounts (is_system=True).
    Returns counts for created/existing.
    """
    rows: Iterable[Dict[str, Any]] = default_coa_rows()

    # existing codes for company
    existing_codes = {
        str(r[0])
        for r in db.query(Account.account_code)
        .filter(Account.company_id == company_id)
        .all()
    }

    to_create = []
    for r in rows:
        code = str(r["account_code"]).strip()
        if not code or code in existing_codes:
            continue

        to_create.append(
            Account(
                company_id=company_id,
                account_code=code,
                name=str(r["name"]).strip(),
                account_type=str(r["account_type"]).strip(),
                normal_balance=str(r["normal_balance"]).strip(),
                is_active=True,
                is_system=True,
            )
        )

    if to_create:
        db.add_all(to_create)

    return {
        "company_id": str(company_id),
        "created": len(to_create),
        "already_present": len(existing_codes),
        "default_total": len(list(rows)),
    }

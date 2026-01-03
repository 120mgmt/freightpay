# services/period_management.py  (FULL FILE — period close & lock enforcement)

from datetime import datetime
from sqlalchemy.orm import Session

from models import AccountingPeriod
from db import db


class PeriodError(Exception):
    pass


def get_or_create_period(*, company_id: int, period: str) -> AccountingPeriod:
    """
    period format: YYYY-MM
    """
    session: Session = db.session

    ap = (
        session.query(AccountingPeriod)
        .filter_by(company_id=company_id, period=period)
        .one_or_none()
    )

    if ap:
        return ap

    ap = AccountingPeriod(
        company_id=company_id,
        period=period,
        status="open",
    )
    session.add(ap)
    session.commit()
    return ap


def close_period(*, company_id: int, period: str, closed_by: str | None = None) -> AccountingPeriod:
    """
    Close a period (no new journals allowed; review state).
    """
    session: Session = db.session

    ap = (
        session.query(AccountingPeriod)
        .filter_by(company_id=company_id, period=period)
        .one_or_none()
    )

    if not ap:
        raise PeriodError("Accounting period not found")

    if ap.status == "locked":
        raise PeriodError("Period is already locked")

    if ap.status == "closed":
        return ap

    ap.status = "closed"
    ap.closed_at = datetime.utcnow()

    session.commit()
    return ap


def lock_period(*, company_id: int, period: str, locked_by: str | None = None) -> AccountingPeriod:
    """
    Lock a period (immutable; historical freeze).
    """
    session: Session = db.session

    ap = (
        session.query(AccountingPeriod)
        .filter_by(company_id=company_id, period=period)
        .one_or_none()
    )

    if not ap:
        raise PeriodError("Accounting period not found")

    if ap.status != "closed":
        raise PeriodError("Period must be closed before locking")

    if ap.status == "locked":
        return ap

    ap.status = "locked"
    ap.locked_at = datetime.utcnow()

    session.commit()
    return ap


def reopen_period(*, company_id: int, period: str) -> AccountingPeriod:
    """
    Reopen a closed period (NOT allowed for locked periods).
    """
    session: Session = db.session

    ap = (
        session.query(AccountingPeriod)
        .filter_by(company_id=company_id, period=period)
        .one_or_none()
    )

    if not ap:
        raise PeriodError("Accounting period not found")

    if ap.status == "locked":
        raise PeriodError("Locked periods cannot be reopened")

    ap.status = "open"
    ap.closed_at = None

    session.commit()
    return ap

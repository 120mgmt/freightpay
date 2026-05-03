# File: bookkeeping/ledger.py
# Purpose: Enterprise-grade persistent ledger service (DB-backed, no in-memory risk)
#          Required for true go-live bookkeeping + 1099 integrity

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, List, Dict

from sqlalchemy.exc import SQLAlchemyError

from db import db


TWOPLACES = Decimal("0.01")


def _utc_now():
    return datetime.now(timezone.utc)


def _to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


class LedgerEntry(db.Model):
    __tablename__ = "ledger_entries"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, index=True, nullable=False)

    entry_type = db.Column(db.String(50), nullable=False, default="payroll")

    pay_period = db.Column(db.String(50), nullable=True)

    contractor_id = db.Column(db.Integer, nullable=True)
    contractor_name = db.Column(db.String(255), nullable=True)

    gross = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    reimbursements = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    deductions = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    net = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    debit_account_code = db.Column(db.String(50), nullable=True)
    credit_account_code = db.Column(db.String(50), nullable=True)

    memo = db.Column(db.Text, nullable=True)

    recorded_by_user_id = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=_utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=_utc_now, onupdate=_utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.id,
            "company_id": self.company_id,
            "entry_type": self.entry_type,
            "pay_period": self.pay_period,
            "contractor_id": self.contractor_id,
            "contractor_name": self.contractor_name,
            "gross": str(self.gross),
            "reimbursements": str(self.reimbursements),
            "deductions": str(self.deductions),
            "net": str(self.net),
            "debit_account_code": self.debit_account_code,
            "credit_account_code": self.credit_account_code,
            "memo": self.memo,
            "recorded_by_user_id": self.recorded_by_user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def record_payroll_run(
    *,
    pay_period: str,
    contractor_id: int,
    gross: Any,
    reimbursements: Any,
    deductions: Any,
    net: Any,
    company_id: int = None,
    contractor_name: str = None,
    recorded_by_user_id: int = None,
) -> Dict[str, Any]:
    """
    Creates a persistent ledger entry for payroll.
    REQUIRED for bookkeeping + 1099 accuracy.
    """

    gross = _to_decimal(gross)
    reimbursements = _to_decimal(reimbursements)
    deductions = _to_decimal(deductions)
    net = _to_decimal(net)

    expected_net = (gross + reimbursements - deductions).quantize(TWOPLACES)
    if expected_net != net:
        raise ValueError("Net does not reconcile with gross + reimbursements - deductions")

    entry = LedgerEntry(
        company_id=company_id or 0,
        entry_type="payroll",
        pay_period=pay_period,
        contractor_id=contractor_id,
        contractor_name=contractor_name,
        gross=gross,
        reimbursements=reimbursements,
        deductions=deductions,
        net=net,
        recorded_by_user_id=recorded_by_user_id,
    )

    try:
        db.session.add(entry)
        db.session.commit()
        return entry.to_dict()
    except SQLAlchemyError as e:
        db.session.rollback()
        raise RuntimeError(f"Ledger write failed: {str(e)}")


def get_ledger(company_id: int = None) -> List[Dict[str, Any]]:
    """
    Returns ledger entries scoped by company.
    """

    query = LedgerEntry.query

    if company_id is not None:
        query = query.filter(LedgerEntry.company_id == company_id)

    rows = query.order_by(LedgerEntry.id.desc()).all()
    return [row.to_dict() for row in rows]


def clear_ledger(company_id: int = None) -> None:
    """
    Dangerous operation — restricted by route layer.
    """

    try:
        query = LedgerEntry.query
        if company_id is not None:
            query = query.filter(LedgerEntry.company_id == company_id)

        query.delete()
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        raise RuntimeError(f"Ledger clear failed: {str(e)}")

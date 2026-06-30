# services/ledger_service.py

from decimal import Decimal
from sqlalchemy.exc import SQLAlchemyError

from db import db
from models.ledger_entry import LedgerEntry  # models/ledger_entry.py (fixed)


class LedgerService:

    @staticmethod
    def create_entry(
        *,
        company_id: int,
        entry_type: str,
        gross: Decimal = Decimal("0"),
        reimbursements: Decimal = Decimal("0"),
        deductions: Decimal = Decimal("0"),
        contractor_id: int | None = None,
        contractor_name: str | None = None,
        debit_account_code: str | None = None,
        credit_account_code: str | None = None,
        memo: str | None = None,
        recorded_by_user_id: int | None = None,
        pay_period: str | None = None,
    ):
        try:
            gross = Decimal(gross or 0)
            reimbursements = Decimal(reimbursements or 0)
            deductions = Decimal(deductions or 0)
            net = gross + reimbursements - deductions

            entry = LedgerEntry(
                company_id=company_id,
                entry_type=entry_type,
                pay_period=pay_period,
                contractor_id=contractor_id,
                contractor_name=contractor_name,
                gross=gross,
                reimbursements=reimbursements,
                deductions=deductions,
                net=net,
                debit_account_code=debit_account_code,
                credit_account_code=credit_account_code,
                memo=memo,
                recorded_by_user_id=recorded_by_user_id,
            )

            db.session.add(entry)
            db.session.commit()
            return entry

        except (ValueError, SQLAlchemyError) as e:
            db.session.rollback()
            raise e

    @staticmethod
    def bulk_create(entries: list[dict]):
        created = []
        try:
            for e in entries:
                entry = LedgerService.create_entry(**e)
                created.append(entry)
            return created
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_company_entries(company_id: int, limit: int = 100):
        return (
            LedgerEntry.query
            .filter(LedgerEntry.company_id == company_id)
            .order_by(LedgerEntry.id.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def delete_entry(entry_id: int, company_id: int):
        entry = LedgerEntry.query.filter_by(
            id=entry_id,
            company_id=company_id
        ).first()
        if not entry:
            return None
        try:
            db.session.delete(entry)
            db.session.commit()
            return True
        except SQLAlchemyError:
            db.session.rollback()
            raise

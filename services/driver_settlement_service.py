# File: services/driver_settlement_service.py
# Purpose: Enterprise-grade immutable Driver Settlement Engine
# Status: FULL production hardened
# Date: 2026-02-25

from __future__ import annotations

import hashlib
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from db import db
from models.driver_settlement import (
    Load,
    DriverAssignment,
    DriverSettlement,
    DriverSettlementLine,
    DriverEscrow,
)
from models.settlement_execution_log import SettlementExecutionLog


class SettlementLockedError(Exception):
    pass


class DuplicateExecutionError(Exception):
    pass


class DriverSettlementService:

    @staticmethod
    def _d(value) -> Decimal:
        return Decimal(str(value or 0)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @staticmethod
    def _hash(company_id: int, driver_id: int, period_label: str) -> str:
        raw = f"{company_id}:{driver_id}:{period_label}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def execute_settlement(
        cls,
        *,
        company_id: int,
        driver_id: int,
        period_label: str,
        executed_by_user_id: int,
        session: Session | None = None,
    ) -> DriverSettlement:

        session = session or db.session

        with session.begin():

            # Idempotency check
            existing_execution = session.execute(
                select(SettlementExecutionLog).where(
                    SettlementExecutionLog.company_id == company_id,
                    SettlementExecutionLog.driver_id == driver_id,
                    SettlementExecutionLog.period_label == period_label,
                ).with_for_update()
            ).scalar_one_or_none()

            if existing_execution:
                raise DuplicateExecutionError("Settlement already executed.")

            # Prevent duplicate settlement header
            existing_settlement = session.execute(
                select(DriverSettlement).where(
                    DriverSettlement.company_id == company_id,
                    DriverSettlement.driver_id == driver_id,
                    DriverSettlement.period_label == period_label,
                ).with_for_update()
            ).scalar_one_or_none()

            if existing_settlement:
                if existing_settlement.locked:
                    raise SettlementLockedError("Settlement is locked.")
                session.delete(existing_settlement)
                session.flush()

            settlement = DriverSettlement(
                company_id=company_id,
                driver_id=driver_id,
                period_label=period_label,
            )
            session.add(settlement)
            session.flush()

            gross_total = Decimal("0.00")
            deduction_total = Decimal("0.00")

            # Lock relevant loads
            loads = session.execute(
                select(Load)
                .join(DriverAssignment, DriverAssignment.load_id == Load.id)
                .where(
                    Load.company_id == company_id,
                    Load.status == "open",
                    DriverAssignment.driver_id == driver_id,
                )
                .with_for_update()
            ).scalars().all()

            for load in loads:

                assignment = session.execute(
                    select(DriverAssignment).where(
                        DriverAssignment.load_id == load.id,
                        DriverAssignment.driver_id == driver_id,
                    )
                ).scalar_one()

                load_revenue = cls._d(load.revenue_amount)
                accessorials = (
                    cls._d(load.fuel_surcharge)
                    + cls._d(load.detention)
                    + cls._d(load.layover)
                    + cls._d(load.other_accessorials)
                )

                if assignment.override_amount:
                    pay_amount = cls._d(assignment.override_amount)

                elif assignment.pay_type == "cpm":
                    pay_amount = cls._d(load.miles) * cls._d(assignment.pay_rate)

                elif assignment.pay_type == "percentage":
                    pay_amount = (load_revenue + accessorials) * cls._d(
                        assignment.pay_rate
                    )

                elif assignment.pay_type == "flat":
                    pay_amount = cls._d(assignment.pay_rate)

                else:
                    pay_amount = Decimal("0.00")

                gross_total += pay_amount

                session.add(
                    DriverSettlementLine(
                        settlement_id=settlement.id,
                        load_id=load.id,
                        description=f"Load {load.load_number}",
                        amount=pay_amount,
                    )
                )

                load.status = "settled"

            # Escrow atomic update
            escrow = session.execute(
                select(DriverEscrow)
                .where(
                    DriverEscrow.company_id == company_id,
                    DriverEscrow.driver_id == driver_id,
                )
                .with_for_update()
            ).scalar_one_or_none()

            if escrow and escrow.balance > 0:
                escrow_deduction = min(cls._d(escrow.balance), gross_total)
                deduction_total += escrow_deduction
                escrow.balance = cls._d(escrow.balance) - escrow_deduction
                escrow.last_updated = datetime.utcnow()

                session.add(
                    DriverSettlementLine(
                        settlement_id=settlement.id,
                        load_id=None,
                        description="Escrow deduction",
                        amount=-escrow_deduction,
                    )
                )

            net_total = gross_total - deduction_total

            settlement.gross_amount = gross_total
            settlement.deductions = deduction_total
            settlement.net_amount = net_total
            settlement.locked = True

            # Execution ledger write
            execution_log = SettlementExecutionLog(
                company_id=company_id,
                driver_id=driver_id,
                period_label=period_label,
                settlement_id=settlement.id,
                executed_by_user_id=executed_by_user_id,
                execution_hash=cls._hash(company_id, driver_id, period_label),
                locked_after_execution=True,
            )

            session.add(execution_log)

        return settlement

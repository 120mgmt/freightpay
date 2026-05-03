# File: payroll/settlement_models.py
# Purpose: In-memory settlement and line-item types for contractor pay engine (no DB).
# Status: Production-safe
# Date: 2026-03-12

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import List


class LineItemType(str, Enum):
    """Type of settlement line item for contractor pay statements."""

    ACCESSORIAL = "accessorial"
    DEDUCTION = "deduction"
    REIMBURSEMENT = "reimbursement"


@dataclass
class SettlementLineItem:
    """Single line item (accessorial, deduction, or reimbursement) on a settlement."""

    code: str
    description: str
    amount: float
    item_type: LineItemType

    def validate(self) -> None:
        """Validate line item (e.g. non-negative amount where applicable)."""
        if self.item_type == LineItemType.DEDUCTION and self.amount < 0:
            raise ValueError("Deduction amount must be >= 0")


@dataclass
class Settlement:
    """Per-driver settlement with line items (accessorials, deductions)."""

    driver_id: str
    line_items: List[SettlementLineItem] = field(default_factory=list)

    def total_accessorials(self) -> Decimal:
        total = Decimal("0")
        for li in self.line_items:
            if li.item_type == LineItemType.ACCESSORIAL:
                total += Decimal(str(li.amount))
        return total

    def total_deductions(self) -> Decimal:
        total = Decimal("0")
        for li in self.line_items:
            if li.item_type == LineItemType.DEDUCTION:
                total += Decimal(str(li.amount))
        return total


__all__ = ["Settlement", "SettlementLineItem", "LineItemType"]

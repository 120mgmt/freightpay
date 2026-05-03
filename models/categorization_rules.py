# freightpay/models/categorization_rules.py
# AUTO-CATEGORIZATION RULES (bank txns + receipts) — engine foundation

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    String,
    Boolean,
    ForeignKey,
    Enum,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from .base import Base


class CategorizationRule(Base):
    __tablename__ = "categorization_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Applies to bank transactions, receipts, or both
    applies_to = Column(
        Enum("bank", "receipt", "both", name="rule_applies_to"),
        nullable=False,
        default="both",
    )

    # Match logic
    match_type = Column(
        Enum(
            "contains",
            "equals",
            "starts_with",
            "ends_with",
            "regex",
            name="rule_match_type",
        ),
        nullable=False,
    )

    match_field = Column(
        Enum(
            "description",
            "vendor",
            "memo",
            name="rule_match_field",
        ),
        nullable=False,
        default="description",
    )

    match_value = Column(String(255), nullable=False)

    # Action (maps to COA)
    expense_account_code = Column(String(50), nullable=False)

    # Optional: set as always "billable" or "review_required"
    review_required = Column(Boolean, nullable=False, default=False)

    is_active = Column(Boolean, nullable=False, default=True)

    created_by = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    company = relationship("Company", backref="categorization_rules")

    __table_args__ = (
        CheckConstraint("length(match_value) > 0", name="ck_rule_match_value_nonempty"),
        CheckConstraint("length(expense_account_code) > 0", name="ck_rule_account_code_nonempty"),
        Index("ix_rules_company_active", "company_id", "is_active"),
        Index("ix_rules_company_applies", "company_id", "applies_to"),
    )

    def as_dict(self) -> dict:
        return {
            "id": str(self.id),
            "company_id": str(self.company_id),
            "applies_to": self.applies_to,
            "match_type": self.match_type,
            "match_field": self.match_field,
            "match_value": self.match_value,
            "expense_account_code": self.expense_account_code,
            "review_required": self.review_required,
            "is_active": self.is_active,
            "created_by": str(self.created_by),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

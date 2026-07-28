# File: models/contractor.py
# Purpose: Enterprise contractor master record for 1099 operations, bookkeeping linkage,
#          audit integrity, and tenant-safe production use.

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlalchemy.orm import validates

from db import db


def _num(value: Any) -> str | None:
    """Numeric -> string for JSON (Decimal is not JSON-serializable)."""
    return None if value is None else str(value)


class Contractor(db.Model):
    __tablename__ = "contractors"

    id = db.Column(db.Integer, primary_key=True)

    # =========================
    # TENANCY / OWNERSHIP
    # =========================
    company_id = db.Column(db.Integer, nullable=False, index=True)

    # =========================
    # IDENTITY / LEGAL
    # =========================
    legal_name = db.Column(db.String(255), nullable=False)
    business_name = db.Column(db.String(255), nullable=True)
    display_name = db.Column(db.String(255), nullable=True)

    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)

    # =========================
    # ADDRESS (1099 + bookkeeping readiness)
    # =========================
    address_line1 = db.Column(db.String(255), nullable=False)
    address_line2 = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(120), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    postal_code = db.Column(db.String(20), nullable=False)
    country = db.Column(db.String(2), nullable=False, default="US", server_default="US")

    # =========================
    # 1099 / TAX CLASSIFICATION
    # =========================
    tax_classification = db.Column(db.String(50), nullable=False)  # individual, sole_prop, llc, partnership, s_corp, c_corp, other
    tin_last4 = db.Column(db.String(4), nullable=True)  # never store full SSN/EIN here
    w9_received = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("false"))
    w9_received_at = db.Column(db.DateTime, nullable=True)
    tin_name_match_verified = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("false"))

    # =========================
    # PAYMENT / OPS DEFAULTS
    # =========================
    payment_method = db.Column(db.String(50), nullable=True)  # ach, check, wire, stripe, external
    payment_terms = db.Column(db.String(50), nullable=True)   # due_on_receipt, net_7, net_15, net_30, custom
    default_currency = db.Column(db.String(3), nullable=False, default="USD", server_default="USD")
    default_expense_account_code = db.Column(db.String(32), nullable=True)
    default_payable_account_code = db.Column(db.String(32), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # =========================
    # STANDING PAY ARRANGEMENT
    # =========================
    # How this driver is normally paid. Individual payroll runs may still
    # override any of these per settlement.
    pay_type = db.Column(db.String(20), nullable=True)  # per_mile, flat, percentage, hourly
    # 4 decimals on purpose: per-mile rates are quoted to 3-4 places ($0.655/mi)
    # and rounding the rate to cents materially changes a settlement.
    rate_per_mile = db.Column(db.Numeric(8, 4), nullable=True)
    flat_rate_per_load = db.Column(db.Numeric(12, 2), nullable=True)
    percentage_of_load = db.Column(db.Numeric(5, 2), nullable=True)  # e.g. 70.00 = 70%
    hourly_rate = db.Column(db.Numeric(10, 2), nullable=True)

    # =========================
    # TRUCK / EQUIPMENT
    # =========================
    truck_number = db.Column(db.String(50), nullable=True)
    truck_vin = db.Column(db.String(17), nullable=True)
    truck_plate = db.Column(db.String(20), nullable=True)
    trailer_number = db.Column(db.String(50), nullable=True)

    # =========================
    # STATUS / LIFECYCLE
    # =========================
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.text("true"), index=True)
    onboarding_status = db.Column(db.String(50), nullable=False, default="draft", server_default="draft")
    deleted_at = db.Column(db.DateTime, nullable=True)

    # =========================
    # AUDIT
    # =========================
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by_user_id = db.Column(db.Integer, nullable=True)
    updated_by_user_id = db.Column(db.Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "email", name="uq_contractors_company_email"),
        UniqueConstraint("company_id", "legal_name", "phone", name="uq_contractors_company_legal_phone"),
        CheckConstraint("char_length(country) = 2", name="ck_contractors_country_len"),
        CheckConstraint("char_length(default_currency) = 3", name="ck_contractors_currency_len"),
        CheckConstraint("tin_last4 IS NULL OR char_length(tin_last4) = 4", name="ck_contractors_tin_last4_len"),
        Index("ix_contractors_company_active_name", "company_id", "is_active", "legal_name"),
        Index("ix_contractors_company_w9_status", "company_id", "w9_received", "is_active"),
        Index("ix_contractors_company_tax_class", "company_id", "tax_classification"),
    )

    # =========================
    # VALIDATION / NORMALIZATION
    # =========================
    @validates("legal_name", "business_name", "display_name", "address_line1", "address_line2", "city", "state", "postal_code", "notes")
    def _normalize_strings(self, key: str, value: Any) -> Any:
        if value is None:
            return None
        value = str(value).strip()
        if key in {"legal_name", "address_line1", "city", "state", "postal_code"} and not value:
            raise ValueError(f"{key} is required")
        return value or None

    @validates("email")
    def _normalize_email(self, key: str, value: Any) -> Any:
        if value is None:
            return None
        value = str(value).strip().lower()
        return value or None

    @validates("phone")
    def _normalize_phone(self, key: str, value: Any) -> Any:
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    @validates("country")
    def _normalize_country(self, key: str, value: Any) -> str:
        if value is None:
            return "US"
        value = str(value).strip().upper()
        if len(value) != 2:
            raise ValueError("country must be a 2-character ISO code")
        return value

    @validates("default_currency")
    def _normalize_currency(self, key: str, value: Any) -> str:
        if value is None:
            return "USD"
        value = str(value).strip().upper()
        if len(value) != 3:
            raise ValueError("default_currency must be a 3-character code")
        return value

    @validates("tax_classification")
    def _validate_tax_classification(self, key: str, value: Any) -> str:
        allowed = {
            "individual",
            "sole_prop",
            "llc",
            "partnership",
            "s_corp",
            "c_corp",
            "nonprofit",
            "other",
        }
        value = (str(value).strip().lower() if value is not None else "")
        if value not in allowed:
            raise ValueError(f"tax_classification must be one of: {', '.join(sorted(allowed))}")
        return value

    @validates("tin_last4")
    def _validate_tin_last4(self, key: str, value: Any) -> Any:
        if value is None or str(value).strip() == "":
            return None
        value = str(value).strip()
        if len(value) != 4 or not value.isdigit():
            raise ValueError("tin_last4 must be exactly 4 digits")
        return value

    @validates("payment_method")
    def _validate_payment_method(self, key: str, value: Any) -> Any:
        if value is None or str(value).strip() == "":
            return None
        value = str(value).strip().lower()
        allowed = {"ach", "check", "wire", "stripe", "external"}
        if value not in allowed:
            raise ValueError(f"payment_method must be one of: {', '.join(sorted(allowed))}")
        return value

    @validates("payment_terms")
    def _validate_payment_terms(self, key: str, value: Any) -> Any:
        if value is None or str(value).strip() == "":
            return None
        value = str(value).strip().lower()
        allowed = {"due_on_receipt", "net_7", "net_15", "net_30", "custom"}
        if value not in allowed:
            raise ValueError(f"payment_terms must be one of: {', '.join(sorted(allowed))}")
        return value

    @validates("onboarding_status")
    def _validate_onboarding_status(self, key: str, value: Any) -> str:
        allowed = {"draft", "pending_w9", "ready", "suspended", "archived"}
        value = (str(value).strip().lower() if value is not None else "draft")
        if value not in allowed:
            raise ValueError(f"onboarding_status must be one of: {', '.join(sorted(allowed))}")
        return value

    # =========================
    # BUSINESS HELPERS
    # =========================
    @property
    def effective_name(self) -> str:
        return self.display_name or self.business_name or self.legal_name

    def mark_w9_received(self, received_at: datetime | None = None) -> None:
        self.w9_received = True
        self.w9_received_at = received_at or datetime.now(timezone.utc)

    def suspend(self, updated_by_user_id: int | None = None) -> None:
        self.is_active = False
        self.onboarding_status = "suspended"
        self.updated_by_user_id = updated_by_user_id

    def activate(self, updated_by_user_id: int | None = None) -> None:
        self.is_active = True
        if self.onboarding_status in {"draft", "pending_w9", "archived"}:
            self.onboarding_status = "ready" if self.w9_received else "pending_w9"
        self.updated_by_user_id = updated_by_user_id

    def soft_delete(self, updated_by_user_id: int | None = None) -> None:
        self.is_active = False
        self.onboarding_status = "archived"
        self.deleted_at = datetime.now(timezone.utc)
        self.updated_by_user_id = updated_by_user_id

    # =========================
    # SERIALIZATION
    # =========================
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "legal_name": self.legal_name,
            "business_name": self.business_name,
            "display_name": self.display_name,
            "effective_name": self.effective_name,
            "email": self.email,
            "phone": self.phone,
            "address": {
                "line1": self.address_line1,
                "line2": self.address_line2,
                "city": self.city,
                "state": self.state,
                "postal_code": self.postal_code,
                "country": self.country,
            },
            "tax": {
                "classification": self.tax_classification,
                "tin_last4": self.tin_last4,
                "w9_received": self.w9_received,
                "w9_received_at": self.w9_received_at.isoformat() if self.w9_received_at else None,
                "tin_name_match_verified": self.tin_name_match_verified,
            },
            "payment": {
                "method": self.payment_method,
                "terms": self.payment_terms,
                "default_currency": self.default_currency,
                "default_expense_account_code": self.default_expense_account_code,
                "default_payable_account_code": self.default_payable_account_code,
            },
            "pay": {
                "pay_type": self.pay_type,
                "rate_per_mile": _num(self.rate_per_mile),
                "flat_rate_per_load": _num(self.flat_rate_per_load),
                "percentage_of_load": _num(self.percentage_of_load),
                "hourly_rate": _num(self.hourly_rate),
            },
            "equipment": {
                "truck_number": self.truck_number,
                "truck_vin": self.truck_vin,
                "truck_plate": self.truck_plate,
                "trailer_number": self.trailer_number,
            },
            "notes": self.notes,
            "is_active": self.is_active,
            "onboarding_status": self.onboarding_status,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by_user_id": self.created_by_user_id,
            "updated_by_user_id": self.updated_by_user_id,
        }

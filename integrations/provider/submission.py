# File: integrations/provider/submission.py
# Purpose: Enterprise Provider Submission Flow (Create + Finalize Payroll)
# Status: Enterprise Hardened (Idempotent, Scoped, Normalized Errors)
# Date: 2026-02-26

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, Any

from flask import Blueprint, request, jsonify
from sqlalchemy import String, DateTime, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import db
from middleware.rbac import require_roles
from middleware.idempotency import require_idempotency

# ============================================================
# BLUEPRINT
# ============================================================

provider_submit_bp = Blueprint(
    "provider_submission",
    __name__,
    url_prefix="/integrations/provider",
)


# ============================================================
# RESPONSE PERSISTENCE (AUDIT + TRACEABILITY)
# ============================================================

def _uuid():
    return uuid.uuid4()


class ProviderSubmissionLog(db.Model):
    __tablename__ = "provider_submission_logs"

    __table_args__ = (
        Index("ix_provider_submission_company", "company_id"),
        Index("ix_provider_submission_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )

    company_id: Mapped[int] = mapped_column(nullable=False, index=True)

    payroll_run_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )

    action: Mapped[str] = mapped_column(String(64), nullable=False)  # create / finalize

    request_payload: Mapped[str] = mapped_column(String, nullable=False)
    response_payload: Mapped[str] = mapped_column(String, nullable=False)

    success: Mapped[bool] = mapped_column(Boolean, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


# ============================================================
# ERROR NORMALIZATION
# ============================================================

def _normalize_error(e: Exception) -> Dict[str, Any]:
    return {
        "error": "provider_submission_failed",
        "detail": str(e),
    }


# ============================================================
# CREATE PAYROLL (PROVIDER)
# ============================================================

@provider_submit_bp.route("/create-payroll", methods=["POST"])
@require_roles(["admin", "finance"])
@require_idempotency
def create_provider_payroll():

    data = request.get_json(force=True)

    company_id = int(data.get("company_id"))
    payroll_run_uuid = uuid.UUID(data.get("payroll_run_uuid"))

    try:
        from payroll.provider import get_payroll_provider

        provider = get_payroll_provider()

        result = provider.run_payroll(data)

        success = True

    except Exception as e:
        result = _normalize_error(e)
        success = False

    with db.session.begin():
        db.session.add(
            ProviderSubmissionLog(
                company_id=company_id,
                payroll_run_uuid=payroll_run_uuid,
                action="create",
                request_payload=str(data),
                response_payload=str(result),
                success=success,
            )
        )

    if not success:
        return jsonify(result), 500

    return jsonify(result), 200


# ============================================================
# FINALIZE PAYROLL (PROVIDER)
# ============================================================

@provider_submit_bp.route("/finalize-payroll", methods=["POST"])
@require_roles(["admin", "finance"])
@require_idempotency
def finalize_provider_payroll():

    data = request.get_json(force=True)

    company_id = int(data.get("company_id"))
    provider_payroll_id = str(data.get("provider_payroll_id")).strip()

    if not provider_payroll_id:
        return jsonify({"error": "missing_provider_payroll_id"}), 400

    try:
        from payroll.provider import get_payroll_provider

        provider = get_payroll_provider()

        result = provider.fetch_payroll_status(provider_payroll_id)

        success = True

    except Exception as e:
        result = _normalize_error(e)
        success = False

    with db.session.begin():
        db.session.add(
            ProviderSubmissionLog(
                company_id=company_id,
                payroll_run_uuid=uuid.uuid4(),  # reference-only for finalize event
                action="finalize",
                request_payload=str(data),
                response_payload=str(result),
                success=success,
            )
        )

    if not success:
        return jsonify(result), 500

    return jsonify(result), 200

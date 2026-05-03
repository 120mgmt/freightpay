# File: routes/payroll_audit_routes.py
# Purpose: Read-only payroll audit access (admin only)
# Status: Production-ready
# Date: 2026-02-18

from __future__ import annotations

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import select

from db import db
from models.payroll_audit_log import PayrollAuditLog

audit_bp = Blueprint("payroll_audit", __name__, url_prefix="/payroll/audit")


@audit_bp.route("/<int:company_id>", methods=["GET"])
@jwt_required()
def get_company_audit(company_id: int):

    identity = get_jwt_identity() or {}
    if identity.get("role") != "admin":
        return jsonify({"error": "ADMIN_REQUIRED"}), 403

    stmt = (
        select(PayrollAuditLog)
        .where(PayrollAuditLog.company_id == company_id)
        .order_by(PayrollAuditLog.created_at.desc())
        .limit(500)
    )
    logs = list(db.session.execute(stmt).scalars().all())

    return jsonify({"logs": [l.to_dict() for l in logs]}), 200

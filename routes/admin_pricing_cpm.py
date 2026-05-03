# routes/admin_pricing_cpm.py
# Admin-only CPM configuration control
# Production-ready
# Date: 2026-01-28

from __future__ import annotations

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from services.pricing_cpm_repo import get_cpm_config, upsert_cpm_config
from utils.admin_audit import log_admin_action


admin_pricing_cpm_bp = Blueprint(
    "admin_pricing_cpm",
    __name__,
    url_prefix="/admin/pricing/cpm",
)


def _require_admin() -> dict:
    ident = get_jwt_identity() or {}
    if not isinstance(ident, dict):
        raise ValueError("Invalid JWT identity")

    role = str(ident.get("role", "")).lower()
    if role not in {"owner", "admin"}:
        raise PermissionError("Admin privileges required")

    if "company_id" not in ident:
        raise ValueError("JWT missing company_id")

    return ident


@admin_pricing_cpm_bp.get("/config")
@jwt_required()
def get_config():
    ident = _require_admin()
    company_id = int(ident["company_id"])

    cfg = get_cpm_config(company_id)
    return jsonify({"company_id": company_id, "config": cfg}), 200


@admin_pricing_cpm_bp.put("/config")
@jwt_required()
def update_config():
    ident = _require_admin()
    payload = request.get_json(force=True) or {}

    company_id = int(ident["company_id"])
    payload["company_id"] = company_id  # enforce scope

    # --- AUDIT (before) ---
    before_cfg = get_cpm_config(company_id)

    cfg = upsert_cpm_config(company_id, payload)

    # --- AUDIT (after) ---
    log_admin_action(
        action="UPDATE",
        resource="CPM_CONFIG",
        before=before_cfg,
        after=cfg,
    )

    return jsonify({"company_id": company_id, "config": cfg}), 200

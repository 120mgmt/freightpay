# freightpay/legal/routes.py
# Purpose: Legal compliance endpoints (Terms, Privacy, Refund)
# Status: Full deployment – production v5
# Date: 2026-01-01

from __future__ import annotations

from flask import Blueprint, jsonify

legal_bp = Blueprint("legal", __name__, url_prefix="/legal")


@legal_bp.get("/terms")
def terms_of_service():
    return jsonify(
        {
            "document": "Terms of Service",
            "version": "v1.0",
            "effective_date": "2026-01-01",
            "content": (
                "FreightPay provides payroll, bookkeeping, and related software services. "
                "By accessing or using FreightPay, you agree to comply with all applicable "
                "laws and regulations. Services are provided on a subscription basis. "
                "Failure to maintain an active subscription may result in suspension or "
                "termination of access. FreightPay does not provide legal or tax advice."
            ),
        }
    ), 200


@legal_bp.get("/privacy")
def privacy_policy():
    return jsonify(
        {
            "document": "Privacy Policy",
            "version": "v1.0",
            "effective_date": "2026-01-01",
            "content": (
                "FreightPay collects only the information necessary to provide its services. "
                "Personal and business data are not sold. Data may be shared with trusted "
                "third-party providers such as Stripe and Gusto solely to perform services. "
                "Reasonable administrative, technical, and physical safeguards are used "
                "to protect user data."
            ),
        }
    ), 200


@legal_bp.get("/refund")
def refund_policy():
    return jsonify(
        {
            "document": "Refund Policy",
            "version": "v1.0",
            "effective_date": "2026-01-01",
            "content": (
                "Subscription fees are billed in advance. Refunds are not provided for "
                "partial billing periods. If FreightPay is unable to provide services due "
                "to system error, billing issues may be reviewed on a case-by-case basis."
            ),
        }
    ), 200

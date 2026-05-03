# routes/contractor.py

from flask import Blueprint, request, jsonify
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from flask_jwt_extended import get_jwt_identity, jwt_required

from db import db
from models.contractor import Contractor

contractor_bp = Blueprint("contractor", __name__, url_prefix="/api/contractors")


def _error(msg, code=400):
    return jsonify({"error": msg}), code


def _get_company_id():
    cid = request.headers.get("X-Company-Id")
    if cid:
        try:
            return int(cid)
        except ValueError:
            return None
    identity = get_jwt_identity()
    if isinstance(identity, dict):
        return identity.get("company_id")
    return None


def _get_user_id():
    identity = get_jwt_identity()
    if isinstance(identity, dict):
        return identity.get("user_id")
    return None


@contractor_bp.get("")
@jwt_required()
def list_contractors():
    company_id = _get_company_id()
    if not company_id:
        return _error("Missing company_id", 403)

    contractors = (
        Contractor.query
        .filter(
            Contractor.company_id == company_id,
            Contractor.deleted_at.is_(None)
        )
        .order_by(Contractor.id.desc())
        .all()
    )

    return jsonify({"contractors": [c.to_dict() for c in contractors]}), 200


@contractor_bp.get("/<int:contractor_id>")
@jwt_required()
def get_contractor(contractor_id):
    company_id = _get_company_id()
    if not company_id:
        return _error("Missing company_id", 403)

    contractor = Contractor.query.filter_by(
        id=contractor_id,
        company_id=company_id
    ).first()

    if not contractor or contractor.deleted_at:
        return _error("Contractor not found", 404)

    return jsonify(contractor.to_dict()), 200


@contractor_bp.post("")
@jwt_required()
def create_contractor():
    company_id = _get_company_id()
    if not company_id:
        return _error("Missing company_id", 403)

    data = request.get_json(silent=True) or {}

    required = [
        "legal_name",
        "address_line1",
        "city",
        "state",
        "postal_code",
        "tax_classification",
    ]

    missing = [k for k in required if not data.get(k)]
    if missing:
        return _error(f"Missing required fields: {missing}")

    try:
        # prevent duplicate contractor (enterprise safety)
        existing = Contractor.query.filter_by(
            company_id=company_id,
            email=data.get("email")
        ).first()

        if existing and data.get("email"):
            return _error("Contractor with this email already exists", 409)

        contractor = Contractor(
            company_id=company_id,
            legal_name=data["legal_name"],
            business_name=data.get("business_name"),
            display_name=data.get("display_name"),
            email=data.get("email"),
            phone=data.get("phone"),
            address_line1=data["address_line1"],
            address_line2=data.get("address_line2"),
            city=data["city"],
            state=data["state"],
            postal_code=data["postal_code"],
            country=data.get("country", "US"),
            tax_classification=data["tax_classification"],
            tin_last4=data.get("tin_last4"),
            payment_method=data.get("payment_method"),
            payment_terms=data.get("payment_terms"),
            default_currency=data.get("default_currency", "USD"),
            default_expense_account_code=data.get("default_expense_account_code"),
            default_payable_account_code=data.get("default_payable_account_code"),
            notes=data.get("notes"),
            created_by_user_id=_get_user_id(),
        )

        db.session.add(contractor)
        db.session.commit()

        return jsonify({"contractor": contractor.to_dict()}), 201

    except IntegrityError:
        db.session.rollback()
        return _error("Duplicate contractor or constraint violation", 409)
    except (ValueError, SQLAlchemyError) as e:
        db.session.rollback()
        return _error(str(e))


@contractor_bp.put("/<int:contractor_id>")
@jwt_required()
def update_contractor(contractor_id):
    company_id = _get_company_id()
    if not company_id:
        return _error("Missing company_id", 403)

    contractor = Contractor.query.filter_by(
        id=contractor_id,
        company_id=company_id
    ).first()

    if not contractor or contractor.deleted_at:
        return _error("Contractor not found", 404)

    data = request.get_json(silent=True) or {}

    try:
        updatable_fields = [
            "legal_name",
            "business_name",
            "display_name",
            "email",
            "phone",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "tax_classification",
            "tin_last4",
            "payment_method",
            "payment_terms",
            "default_currency",
            "default_expense_account_code",
            "default_payable_account_code",
            "notes",
        ]

        for field in updatable_fields:
            if field in data:
                setattr(contractor, field, data[field])

        contractor.updated_by_user_id = _get_user_id()

        db.session.commit()

        return jsonify({"contractor": contractor.to_dict()}), 200

    except IntegrityError:
        db.session.rollback()
        return _error("Constraint violation during update", 409)
    except (ValueError, SQLAlchemyError) as e:
        db.session.rollback()
        return _error(str(e))


@contractor_bp.delete("/<int:contractor_id>")
@jwt_required()
def delete_contractor(contractor_id):
    company_id = _get_company_id()
    if not company_id:
        return _error("Missing company_id", 403)

    contractor = Contractor.query.filter_by(
        id=contractor_id,
        company_id=company_id
    ).first()

    if not contractor or contractor.deleted_at:
        return _error("Contractor not found", 404)

    try:
        contractor.soft_delete(updated_by_user_id=_get_user_id())
        db.session.commit()
        return jsonify({"status": "deleted"}), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return _error(str(e))

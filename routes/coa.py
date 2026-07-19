# File: routes/coa.py
# Purpose: Chart of Accounts + manual transactions API (company-scoped)
# Status: Production-ready (crash-resistant imports, strict company_id parsing)
# Date: 2026-02-14 (transactions added 2026-07-19)

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from db import db
from models.chart_of_accounts import ACCOUNT_TYPES, Account
from models.ledger import Journal, LedgerEntry
from utils.plan_access import require_plan

coa_bp = Blueprint("coa_bp", __name__, url_prefix="/coa")

# An account's normal balance is implied by its type (standard accounting):
# assets & expenses increase on the debit side; the rest on the credit side.
_NORMAL_BALANCE_BY_TYPE = {
    "asset": "debit",
    "expense": "debit",
    "liability": "credit",
    "equity": "credit",
    "revenue": "credit",
}


def _require_company_id() -> int:
    cid = request.headers.get("X-Company-Id")
    if cid is None or str(cid).strip() == "":
        cid = request.args.get("company_id")

    if cid is None or str(cid).strip() == "":
        data = request.get_json(silent=True) or {}
        cid = data.get("company_id") if isinstance(data, dict) else None

    if cid is None or str(cid).strip() == "":
        raise ValueError("company_id_required")

    try:
        v = int(str(cid).strip())
        if v <= 0:
            raise ValueError("company_id_required")
        return v
    except Exception:
        raise ValueError("company_id_required")


@coa_bp.route("/seed", methods=["POST"])
@require_plan("bookkeeping")
def seed_coa():
    try:
        company_id = _require_company_id()

        # Lazy import to avoid app boot crash if service layer changes during deploys
        from services.coa import seed_default_coa  # type: ignore

        result = seed_default_coa(db.session, company_id=company_id)
        # The service only flushes; without an explicit commit the request
        # teardown rolls everything back and the seed silently vanishes.
        db.session.commit()
        return jsonify(result), 200
    except ValueError:
        db.session.rollback()
        return jsonify({"error": "company_id_required"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "seed_failed", "detail": str(e)}), 500


@coa_bp.route("/accounts", methods=["GET"])
@require_plan("bookkeeping")
def list_accounts():
    try:
        company_id = _require_company_id()
        stmt = (
            select(Account)
            .where(Account.company_id == company_id)
            .order_by(Account.account_code.asc(), Account.id.asc())
        )
        accounts = list(db.session.execute(stmt).scalars().all())
        return jsonify([a.as_dict() for a in accounts]), 200
    except ValueError:
        return jsonify({"error": "company_id_required"}), 400
    except Exception as e:
        return jsonify({"error": "list_failed", "detail": str(e)}), 500


@coa_bp.route("/accounts", methods=["POST"])
@require_plan("bookkeeping")
def create_account():
    """
    Add a single custom account to the company's chart of accounts.

    Body: {"account_code": "6100", "name": "Fuel", "account_type": "expense"}
    normal_balance is derived from account_type automatically.
    """
    try:
        company_id = _require_company_id()
    except ValueError:
        return jsonify({"error": "company_id_required"}), 400

    data = request.get_json(silent=True) or {}
    code = str(data.get("account_code") or "").strip()
    name = str(data.get("name") or "").strip()
    acct_type = str(data.get("account_type") or "").strip().lower()

    if not code:
        return jsonify({"error": "account_code_required"}), 400
    if not name:
        return jsonify({"error": "name_required"}), 400
    if acct_type not in ACCOUNT_TYPES:
        return jsonify({"error": "invalid_account_type", "allowed": list(ACCOUNT_TYPES)}), 400
    if len(code) > 50 or len(name) > 120:
        return jsonify({"error": "field_too_long"}), 400

    # Reject duplicates up front for a clean message (a DB unique constraint
    # also guards this at the company+code level).
    existing = db.session.execute(
        select(Account).where(
            Account.company_id == company_id,
            Account.account_code == code,
        )
    ).scalar_one_or_none()
    if existing:
        return jsonify({"error": "account_code_exists", "detail": f"Account code {code} already exists."}), 409

    account = Account(
        company_id=company_id,
        account_code=code,
        name=name,
        account_type=acct_type,
        normal_balance=_NORMAL_BALANCE_BY_TYPE[acct_type],
        is_system=False,
        is_active=True,
    )
    try:
        db.session.add(account)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "create_failed", "detail": str(e)}), 500

    return jsonify(account.as_dict()), 201



# ============================================================
# Manual transactions (expenses / income) — post to the ledger
# ============================================================

def _txn_kind(journal: Journal) -> str:
    sid = journal.source_id or ""
    return sid.split(":", 1)[0] if ":" in sid else "expense"


def _journal_summary(journal: Journal) -> dict:
    """Flatten a manual journal into a transaction row for the UI."""
    kind = _txn_kind(journal)
    amount = "0.00"
    category = None
    paid_via = None
    vendor = None
    for e in journal.entries:
        side_amt = e.debit if e.debit and e.debit > 0 else e.credit
        acct = {"account_code": e.account_code, "name": e.account.name if e.account else e.account_code}
        is_category = (
            (kind == "expense" and e.debit and e.debit > 0)
            or (kind == "income" and e.credit and e.credit > 0)
        )
        if is_category:
            category = acct
            amount = str(side_amt)
        else:
            paid_via = acct
        if e.memo and not vendor:
            vendor = e.memo
    return {
        "id": int(journal.id),
        "type": kind,
        "date": journal.posted_at.date().isoformat() if journal.posted_at else None,
        "accounting_period": journal.accounting_period,
        "description": journal.description,
        "amount": amount,
        "category": category,
        "paid_via": paid_via,
        "vendor": vendor,
    }


@coa_bp.route("/transactions", methods=["GET"])
@require_plan("bookkeeping")
def list_transactions():
    try:
        company_id = _require_company_id()
    except ValueError:
        return jsonify({"error": "company_id_required"}), 400

    try:
        page = max(1, int(request.args.get("page", 1)))
    except Exception:
        page = 1
    per_page = 50

    base = (
        select(Journal)
        .where(Journal.company_id == company_id, Journal.source_type == "manual")
        .order_by(Journal.posted_at.desc(), Journal.id.desc())
    )
    journals = list(
        db.session.execute(base.offset((page - 1) * per_page).limit(per_page)).scalars().all()
    )
    from sqlalchemy import func as _func

    total = db.session.execute(
        select(_func.count(Journal.id)).where(
            Journal.company_id == company_id, Journal.source_type == "manual"
        )
    ).scalar() or 0

    return jsonify(
        {
            "total": int(total),
            "page": page,
            "per_page": per_page,
            "transactions": [_journal_summary(j) for j in journals],
        }
    ), 200


@coa_bp.route("/transactions", methods=["POST"])
@require_plan("bookkeeping")
def create_transaction():
    """
    Record a single expense or income as a balanced double-entry journal.

    Body: {
      "type": "expense" | "income",
      "date": "YYYY-MM-DD",
      "amount": 125.50,
      "account_code": "6100",          # expense account (or revenue for income)
      "payment_account_code": "1000",  # asset account money moved through
      "description": "Fuel — TA Travel Center",
      "vendor": "TA"                    # optional
    }
    """
    try:
        company_id = _require_company_id()
    except ValueError:
        return jsonify({"error": "company_id_required"}), 400

    data = request.get_json(silent=True) or {}
    kind = str(data.get("type") or "").strip().lower()
    if kind not in ("expense", "income"):
        return jsonify({"error": "invalid_type", "allowed": ["expense", "income"]}), 400

    date_str = str(data.get("date") or "").strip()
    try:
        txn_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
            hour=12, tzinfo=timezone.utc
        )
    except Exception:
        return jsonify({"error": "invalid_date", "detail": "Use YYYY-MM-DD."}), 400

    try:
        amount = Decimal(str(data.get("amount"))).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        return jsonify({"error": "invalid_amount"}), 400
    if amount <= 0:
        return jsonify({"error": "invalid_amount", "detail": "Amount must be greater than zero."}), 400

    description = str(data.get("description") or "").strip()
    if not description:
        return jsonify({"error": "description_required"}), 400
    vendor = (str(data.get("vendor") or "").strip() or None)

    def _account(code_field: str):
        code = str(data.get(code_field) or "").strip()
        if not code:
            return None, jsonify({"error": f"{code_field}_required"}), 400
        acct = db.session.execute(
            select(Account).where(
                Account.company_id == company_id, Account.account_code == code
            )
        ).scalar_one_or_none()
        if not acct:
            return None, jsonify({"error": "account_not_found", "account_code": code}), 404
        return acct, None, None

    category, err, code = _account("account_code")
    if err:
        return err, code
    payment, err, code = _account("payment_account_code")
    if err:
        return err, code

    expected_type = "expense" if kind == "expense" else "revenue"
    if category.account_type != expected_type:
        return jsonify(
            {
                "error": "wrong_account_type",
                "detail": f"Pick an {expected_type} account for the category "
                f"({category.account_code} is {category.account_type}).",
            }
        ), 400
    if payment.account_type != "asset":
        return jsonify(
            {
                "error": "wrong_account_type",
                "detail": f"The paid-from account must be an asset account like Cash or a bank "
                f"({payment.account_code} is {payment.account_type}).",
            }
        ), 400

    journal = Journal(
        company_id=company_id,
        source_type="manual",
        source_id=f"{kind}:{uuid.uuid4()}",
        accounting_period=date_str[:7],
        description=description[:255],
        posted_at=txn_date,
    )
    try:
        from utils.auth import get_current_user

        me = get_current_user()
        if me:
            journal.posted_by = me.id
    except Exception:
        pass

    # Double entry: expense debits the expense account and credits the asset;
    # income debits the asset and credits the revenue account.
    if kind == "expense":
        debit_acct, credit_acct = category, payment
    else:
        debit_acct, credit_acct = payment, category

    journal.entries = [
        LedgerEntry(
            company_id=company_id,
            account_id=debit_acct.id,
            account_code=debit_acct.account_code,
            debit=amount,
            credit=Decimal("0.00"),
            memo=vendor,
        ),
        LedgerEntry(
            company_id=company_id,
            account_id=credit_acct.id,
            account_code=credit_acct.account_code,
            debit=Decimal("0.00"),
            credit=amount,
            memo=vendor,
        ),
    ]

    try:
        db.session.add(journal)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "create_failed", "detail": str(e)}), 500

    return jsonify(_journal_summary(journal)), 201


@coa_bp.route("/transactions/<int:journal_id>", methods=["DELETE"])
@require_plan("bookkeeping")
def delete_transaction(journal_id: int):
    """Delete a manually recorded transaction (manual journals only)."""
    try:
        company_id = _require_company_id()
    except ValueError:
        return jsonify({"error": "company_id_required"}), 400

    journal = db.session.get(Journal, journal_id)
    if not journal or journal.company_id != company_id:
        return jsonify({"error": "transaction_not_found"}), 404
    if journal.source_type != "manual":
        return jsonify(
            {"error": "not_deletable", "detail": "Only manually recorded transactions can be deleted."}
        ), 400

    try:
        db.session.delete(journal)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "delete_failed", "detail": str(e)}), 500

    return jsonify({"status": "deleted", "id": journal_id}), 200

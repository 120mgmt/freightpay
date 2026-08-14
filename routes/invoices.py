# File: routes/invoices.py
# Purpose: Client invoicing — create, email (Brevo SMTP), collect via a Stripe
#          payment link, and track paid vs unpaid.
# Status: Production-ready (company-scoped, plan-gated, degrades without Stripe/SMTP)

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required, verify_jwt_in_request
from sqlalchemy import func, select

from db import db
from models.client_invoice import ClientInvoice, ClientInvoiceItem
from utils.plan_access import require_plan

invoices_api_bp = Blueprint("invoices_api", __name__, url_prefix="/api/invoices")

TWOPLACES = Decimal("0.01")


def _json_error(message: str, status: int = 400, code: str = "BAD_REQUEST", **extra: Any):
    payload: dict[str, Any] = {"error": code, "message": message}
    payload.update(extra)
    return jsonify(payload), status


def _require_auth():
    """JWT + company scope; an X-Company-Id that disagrees with the token is rejected."""
    verify_jwt_in_request()
    identity = get_jwt_identity()
    if not identity or not isinstance(identity, dict):
        return None, _json_error("Authentication required", 401, "UNAUTHORIZED")

    company_id = identity.get("company_id")
    user_id = identity.get("user_id") or identity.get("id")

    header_company_id = request.headers.get("X-Company-Id")
    if header_company_id:
        try:
            header_company_id = int(str(header_company_id).strip())
        except (TypeError, ValueError):
            return None, _json_error("Invalid X-Company-Id header", 400, "INVALID_COMPANY_ID")
        if company_id is not None and int(company_id) != header_company_id:
            return None, _json_error("Company scope mismatch", 403, "FORBIDDEN")
        company_id = header_company_id

    try:
        company_id = int(company_id)
    except (TypeError, ValueError):
        return None, _json_error("Company context is required", 403, "FORBIDDEN")

    return {"company_id": company_id, "user_id": user_id}, None


def _money(value: Any, field: str) -> Decimal:
    try:
        d = Decimal(str(value if value not in (None, "") else 0))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field} must be a number")
    return d.quantize(TWOPLACES)


def _parse_date(value: Any, field: str, required: bool = False) -> Optional[date]:
    raw = str(value or "").strip()
    if not raw:
        if required:
            raise ValueError(f"{field} is required")
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"{field} must be YYYY-MM-DD")


def _next_invoice_number(company_id: int) -> str:
    """
    Sequential per company: INV-1001, INV-1002…

    Derived from the highest existing number rather than a global counter so
    two companies never see each other's sequence.
    """
    rows = db.session.execute(
        select(ClientInvoice.invoice_number).where(ClientInvoice.company_id == company_id)
    ).scalars().all()
    highest = 1000
    for num in rows:
        digits = "".join(ch for ch in str(num) if ch.isdigit())
        if digits:
            try:
                highest = max(highest, int(digits))
            except ValueError:
                continue
    return f"INV-{highest + 1}"


def _build_items(raw_items: Any) -> tuple[list[ClientInvoiceItem], Decimal]:
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("Add at least one line item")

    items: list[ClientInvoiceItem] = []
    subtotal = Decimal("0.00")

    for idx, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            raise ValueError(f"Line {idx + 1} is not valid")
        description = str(raw.get("description") or "").strip()
        if not description:
            raise ValueError(f"Line {idx + 1} needs a description")

        quantity = _money(raw.get("quantity", 1), f"Line {idx + 1} quantity")
        unit_price = _money(raw.get("unit_price", 0), f"Line {idx + 1} rate")
        if quantity < 0 or unit_price < 0:
            raise ValueError(f"Line {idx + 1} cannot be negative")

        amount = (quantity * unit_price).quantize(TWOPLACES)
        subtotal += amount
        items.append(
            ClientInvoiceItem(
                description=description[:500],
                quantity=quantity,
                unit_price=unit_price,
                amount=amount,
                sort_order=idx,
            )
        )

    return items, subtotal.quantize(TWOPLACES)


def _load_invoice(company_id: int, invoice_id: int) -> Optional[ClientInvoice]:
    return db.session.execute(
        select(ClientInvoice).where(
            ClientInvoice.id == invoice_id, ClientInvoice.company_id == company_id
        )
    ).scalar_one_or_none()


# ------------------------------------------------------------------
# Stripe payment link
# ------------------------------------------------------------------
def _stripe():
    """Stripe client, or None when no key is configured (invoicing still works)."""
    try:
        import stripe  # type: ignore
    except Exception:
        return None
    secret = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
    if not secret.startswith(("sk_live_", "sk_test_")):
        return None
    stripe.api_key = secret
    return stripe


def _ensure_payment_link(invoice: ClientInvoice) -> Optional[str]:
    """
    Create a reusable Stripe payment link for the invoice total.

    Returns the URL, or None when Stripe is not configured — an invoice can
    always be created and emailed; the payment link is an enhancement.
    """
    if invoice.stripe_payment_link_url:
        return invoice.stripe_payment_link_url
    if invoice.total is None or invoice.total <= 0:
        return None

    stripe = _stripe()
    if stripe is None:
        return None

    try:
        price = stripe.Price.create(
            unit_amount=int((invoice.total * 100).quantize(Decimal("1"))),
            currency=(invoice.currency or "USD").lower(),
            product_data={"name": f"Invoice {invoice.invoice_number}"},
        )
        link = stripe.PaymentLink.create(
            line_items=[{"price": price["id"], "quantity": 1}],
            metadata={
                "ledgerhaul_invoice_id": str(invoice.id),
                "ledgerhaul_company_id": str(invoice.company_id),
                "invoice_number": invoice.invoice_number,
            },
        )
        invoice.stripe_payment_link_id = link["id"]
        invoice.stripe_payment_link_url = link["url"]
        return link["url"]
    except Exception:
        # A Stripe problem must not block sending the invoice.
        return None


# ------------------------------------------------------------------
# Revenue recognition
#
# A paid invoice posts a balanced journal — debit cash, credit revenue — so it
# flows into the P&L automatically. Two things keep this safe:
#   * journal_id makes it idempotent (marking paid twice books revenue once)
#   * source_type "invoice" keeps these out of the Bookkeeping transactions
#     list, which filters on "manual", so they can't be edited or deleted
#     there and get out of step with the invoice.
# ------------------------------------------------------------------
def _pick_account(company_id: int, account_type: str, preferred_code: str):
    """Preferred default account for a type, else the first active one."""
    from models.chart_of_accounts import Account

    account = db.session.execute(
        select(Account).where(
            Account.company_id == company_id,
            Account.account_code == preferred_code,
            Account.account_type == account_type,
            Account.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if account:
        return account

    return db.session.execute(
        select(Account)
        .where(
            Account.company_id == company_id,
            Account.account_type == account_type,
            Account.is_active.is_(True),
        )
        .order_by(Account.account_code.asc())
    ).scalars().first()


def _apply_payment(invoice: ClientInvoice, amount: Decimal, user_id: Any = None) -> None:
    """Mark an invoice paid and book the revenue. Shared by mark-paid, the
    manual sync-payment poll, and the Stripe webhook so all three paths
    apply a payment identically."""
    invoice.amount_paid = amount
    invoice.status = "paid"
    invoice.paid_at = datetime.now(timezone.utc)
    _post_invoice_journal(invoice, user_id)


def apply_invoice_checkout_payment(session_obj: dict) -> bool:
    """
    Entry point for billing/webhooks.py: a checkout.session.completed (or
    .async_payment_succeeded) event whose metadata identifies one of our
    invoice payment links (set in _ensure_payment_link) marks that invoice
    paid immediately, instead of requiring the manual "check payment" click.

    Returns False when the session isn't for one of our invoices — Stripe's
    subscription checkout sessions carry no such metadata — so the webhook
    can fall through to its normal subscription handling. Commits its own
    transaction; the caller only needs to catch exceptions.
    """
    metadata = session_obj.get("metadata") or {}
    invoice_id_raw = metadata.get("ledgerhaul_invoice_id")
    if not invoice_id_raw:
        return False
    try:
        invoice_id = int(invoice_id_raw)
    except (TypeError, ValueError):
        return False

    if session_obj.get("payment_status") != "paid":
        return False

    invoice = db.session.get(ClientInvoice, invoice_id)
    if not invoice:
        return False

    # Defense in depth: the metadata is ours, but confirm the company still
    # matches before mutating anything.
    company_meta = metadata.get("ledgerhaul_company_id")
    if company_meta and str(invoice.company_id) != str(company_meta):
        return False

    if invoice.status == "paid":
        return True  # already applied — idempotent against Stripe retries

    amount_total = session_obj.get("amount_total")
    amount = (
        (Decimal(str(amount_total)) / 100).quantize(TWOPLACES)
        if amount_total is not None
        else invoice.total
    )
    _apply_payment(invoice, amount)
    db.session.commit()
    return True


def _post_invoice_journal(invoice: ClientInvoice, user_id: Any) -> Optional[int]:
    """
    Book the revenue for a paid invoice.

    Returns the journal id, or None when it was skipped — a company that has
    not set up its chart of accounts should still be able to mark an invoice
    paid; the books simply do not move.
    """
    if invoice.journal_id:
        return invoice.journal_id

    amount = invoice.amount_paid or Decimal("0.00")
    if amount <= 0:
        return None

    from models.ledger import Journal, LedgerEntry

    cash = _pick_account(invoice.company_id, "asset", "1000")
    revenue = _pick_account(invoice.company_id, "revenue", "4000")
    if not cash or not revenue:
        return None

    posted_at = invoice.paid_at or datetime.now(timezone.utc)
    journal = Journal(
        company_id=invoice.company_id,
        source_type="invoice",
        source_id=f"invoice:{invoice.id}",
        accounting_period=posted_at.strftime("%Y-%m"),
        description=f"Invoice {invoice.invoice_number} — {invoice.client_name}"[:255],
        posted_at=posted_at,
        posted_by=user_id if isinstance(user_id, int) else None,
    )
    journal.entries = [
        LedgerEntry(
            company_id=invoice.company_id,
            account_id=cash.id,
            account_code=cash.account_code,
            debit=amount,
            credit=Decimal("0.00"),
            memo=invoice.client_name[:255] if invoice.client_name else None,
        ),
        LedgerEntry(
            company_id=invoice.company_id,
            account_id=revenue.id,
            account_code=revenue.account_code,
            debit=Decimal("0.00"),
            credit=amount,
            memo=invoice.client_name[:255] if invoice.client_name else None,
        ),
    ]

    db.session.add(journal)
    db.session.flush()  # need the id before the caller commits
    invoice.journal_id = journal.id
    return journal.id


def _reverse_invoice_journal(invoice: ClientInvoice) -> None:
    """Un-book revenue when a paid invoice is voided."""
    if not invoice.journal_id:
        return

    from models.ledger import Journal

    journal = db.session.get(Journal, invoice.journal_id)
    # Only ever remove a journal this invoice created.
    if journal and journal.source_type == "invoice" and journal.company_id == invoice.company_id:
        db.session.delete(journal)
    invoice.journal_id = None


def _invoice_email_html(invoice: ClientInvoice, company_name: str) -> str:
    rows = "".join(
        f"<tr>"
        f"<td style='padding:8px 0;border-bottom:1px solid #eee'>{i.description}</td>"
        f"<td style='padding:8px 0;border-bottom:1px solid #eee;text-align:right'>{i.quantity}</td>"
        f"<td style='padding:8px 0;border-bottom:1px solid #eee;text-align:right'>${i.unit_price}</td>"
        f"<td style='padding:8px 0;border-bottom:1px solid #eee;text-align:right'>${i.amount}</td>"
        f"</tr>"
        for i in invoice.items
    )
    pay_button = ""
    if invoice.stripe_payment_link_url:
        pay_button = (
            f"<p style='margin:24px 0'>"
            f"<a href='{invoice.stripe_payment_link_url}' "
            f"style='background:#0f766e;color:#fff;padding:12px 20px;border-radius:8px;"
            f"text-decoration:none;font-weight:600'>Pay ${invoice.total} online</a></p>"
        )
    due = f"<p style='color:#555'>Due {invoice.due_date.isoformat()}</p>" if invoice.due_date else ""
    notes = (
        f"<p style='color:#555;white-space:pre-wrap'>{invoice.notes}</p>" if invoice.notes else ""
    )

    return f"""
    <div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:0 auto;color:#111">
      <h2 style="margin:0 0 4px">Invoice {invoice.invoice_number}</h2>
      <p style="margin:0 0 16px;color:#555">From {company_name}</p>
      {due}
      <table style="width:100%;border-collapse:collapse;font-size:14px">
        <thead>
          <tr style="text-align:left;color:#666">
            <th style="padding:8px 0;border-bottom:2px solid #ddd">Description</th>
            <th style="padding:8px 0;border-bottom:2px solid #ddd;text-align:right">Qty</th>
            <th style="padding:8px 0;border-bottom:2px solid #ddd;text-align:right">Rate</th>
            <th style="padding:8px 0;border-bottom:2px solid #ddd;text-align:right">Amount</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <p style="text-align:right;font-size:18px;font-weight:700;margin:16px 0 0">
        Total ${invoice.total}
      </p>
      {pay_button}
      {notes}
      <p style="color:#999;font-size:12px;margin-top:32px">Sent with LedgerHaul</p>
    </div>
    """


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------
@invoices_api_bp.get("")
@jwt_required()
@require_plan("bookkeeping")
def list_invoices():
    auth, err = _require_auth()
    if err:
        return err
    company_id = auth["company_id"]

    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = min(100, max(1, int(request.args.get("per_page", 50))))
    except (TypeError, ValueError):
        per_page = 50

    conds = [ClientInvoice.company_id == company_id]

    status = (request.args.get("status") or "").strip().lower()
    if status in ("draft", "sent", "paid", "void"):
        conds.append(ClientInvoice.status == status)
    elif status == "overdue":
        conds.extend(
            [
                ClientInvoice.status == "sent",
                ClientInvoice.due_date.isnot(None),
                ClientInvoice.due_date < date.today(),
            ]
        )

    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        conds.append(
            ClientInvoice.client_name.ilike(like)
            | ClientInvoice.invoice_number.ilike(like)
            | ClientInvoice.client_email.ilike(like)
        )

    base = select(ClientInvoice)
    count_q = select(func.count(ClientInvoice.id))
    for c in conds:
        base = base.where(c)
        count_q = count_q.where(c)

    total_count = db.session.execute(count_q).scalar() or 0
    rows = db.session.execute(
        base.order_by(ClientInvoice.issue_date.desc(), ClientInvoice.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).scalars().all()

    # Dashboard figures cover the whole company, not just this page.
    def _sum_where(*extra):
        stmt = select(func.coalesce(func.sum(ClientInvoice.total), 0)).where(
            ClientInvoice.company_id == company_id
        )
        for e in extra:
            stmt = stmt.where(e)
        return db.session.execute(stmt).scalar() or Decimal("0.00")

    outstanding = _sum_where(ClientInvoice.status == "sent")
    paid_total = _sum_where(ClientInvoice.status == "paid")
    overdue = _sum_where(
        ClientInvoice.status == "sent",
        ClientInvoice.due_date.isnot(None),
        ClientInvoice.due_date < date.today(),
    )

    return jsonify(
        {
            "total": int(total_count),
            "page": page,
            "per_page": per_page,
            "summary": {
                "outstanding": str(outstanding),
                "paid": str(paid_total),
                "overdue": str(overdue),
            },
            "invoices": [inv.to_dict() for inv in rows],
        }
    ), 200


@invoices_api_bp.post("")
@jwt_required()
@require_plan("bookkeeping")
def create_invoice():
    auth, err = _require_auth()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    client_name = str(data.get("client_name") or "").strip()
    if not client_name:
        return _json_error("Who is this invoice for? Add a client name.", 400, "CLIENT_REQUIRED")

    try:
        items, subtotal = _build_items(data.get("items"))
        issue_date = _parse_date(data.get("issue_date"), "Issue date") or date.today()
        due_date = _parse_date(data.get("due_date"), "Due date")
        tax = _money(data.get("tax", 0), "Tax")
    except ValueError as exc:
        return _json_error(str(exc), 400, "VALIDATION_ERROR")

    if tax < 0:
        return _json_error("Tax cannot be negative", 400, "VALIDATION_ERROR")
    if due_date and due_date < issue_date:
        return _json_error("Due date cannot be before the issue date", 400, "VALIDATION_ERROR")

    invoice = ClientInvoice(
        company_id=auth["company_id"],
        invoice_number=_next_invoice_number(auth["company_id"]),
        client_name=client_name[:255],
        client_email=(str(data.get("client_email") or "").strip() or None),
        client_address=(str(data.get("client_address") or "").strip() or None),
        issue_date=issue_date,
        due_date=due_date,
        status="draft",
        subtotal=subtotal,
        tax=tax,
        total=(subtotal + tax).quantize(TWOPLACES),
        amount_paid=Decimal("0.00"),
        notes=(str(data.get("notes") or "").strip() or None),
        created_by_user_id=auth["user_id"] if isinstance(auth["user_id"], int) else None,
        items=items,
    )

    try:
        db.session.add(invoice)
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return _json_error(f"Could not create the invoice: {exc}", 500, "CREATE_FAILED")

    return jsonify(invoice.to_dict()), 201


@invoices_api_bp.get("/<int:invoice_id>")
@jwt_required()
@require_plan("bookkeeping")
def get_invoice(invoice_id: int):
    auth, err = _require_auth()
    if err:
        return err
    invoice = _load_invoice(auth["company_id"], invoice_id)
    if not invoice:
        return _json_error("Invoice not found", 404, "NOT_FOUND")
    return jsonify(invoice.to_dict()), 200


@invoices_api_bp.patch("/<int:invoice_id>")
@jwt_required()
@require_plan("bookkeeping")
def update_invoice(invoice_id: int):
    auth, err = _require_auth()
    if err:
        return err
    invoice = _load_invoice(auth["company_id"], invoice_id)
    if not invoice:
        return _json_error("Invoice not found", 404, "NOT_FOUND")
    if invoice.status in ("paid", "void"):
        return _json_error(
            f"A {invoice.status} invoice can no longer be edited", 409, "NOT_EDITABLE"
        )

    data = request.get_json(silent=True) or {}

    try:
        if "items" in data:
            items, subtotal = _build_items(data.get("items"))
            invoice.items = items
            invoice.subtotal = subtotal
        if "issue_date" in data:
            invoice.issue_date = _parse_date(data.get("issue_date"), "Issue date") or invoice.issue_date
        if "due_date" in data:
            invoice.due_date = _parse_date(data.get("due_date"), "Due date")
        if "tax" in data:
            invoice.tax = _money(data.get("tax", 0), "Tax")
    except ValueError as exc:
        return _json_error(str(exc), 400, "VALIDATION_ERROR")

    for field, attr in (
        ("client_name", "client_name"),
        ("client_email", "client_email"),
        ("client_address", "client_address"),
        ("notes", "notes"),
    ):
        if field in data:
            value = str(data.get(field) or "").strip() or None
            if field == "client_name" and not value:
                return _json_error("Client name cannot be blank", 400, "CLIENT_REQUIRED")
            setattr(invoice, attr, value)

    invoice.total = ((invoice.subtotal or Decimal("0.00")) + (invoice.tax or Decimal("0.00"))).quantize(
        TWOPLACES
    )

    # The stored link is for the old amount — drop it so the next send regenerates.
    if "items" in data or "tax" in data:
        invoice.stripe_payment_link_id = None
        invoice.stripe_payment_link_url = None

    try:
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return _json_error(f"Could not update the invoice: {exc}", 500, "UPDATE_FAILED")

    return jsonify(invoice.to_dict()), 200


@invoices_api_bp.post("/<int:invoice_id>/send")
@jwt_required()
@require_plan("bookkeeping")
def send_invoice(invoice_id: int):
    """Email the invoice to the client with a Stripe payment link attached."""
    auth, err = _require_auth()
    if err:
        return err
    invoice = _load_invoice(auth["company_id"], invoice_id)
    if not invoice:
        return _json_error("Invoice not found", 404, "NOT_FOUND")
    if invoice.status == "void":
        return _json_error("This invoice has been voided", 409, "VOIDED")

    to_email = (request.get_json(silent=True) or {}).get("email") or invoice.client_email
    to_email = str(to_email or "").strip()
    if not to_email or "@" not in to_email:
        return _json_error(
            "Add the client's email address before sending", 400, "EMAIL_REQUIRED"
        )

    payment_url = _ensure_payment_link(invoice)

    company_name = "LedgerHaul"
    try:
        from models.company import Company

        company = db.session.get(Company, invoice.company_id)
        if company and company.name:
            company_name = company.name
    except Exception:
        pass

    from utils.mailer import send_email, smtp_configured

    if not smtp_configured():
        # Still record the link so it can be shared manually.
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return _json_error(
            "Email is not configured yet. Add your Brevo SMTP details in "
            "Admin → Settings, or copy the payment link and send it yourself.",
            503,
            "SMTP_NOT_CONFIGURED",
            payment_link_url=payment_url,
        )

    try:
        send_email(
            to_email,
            f"Invoice {invoice.invoice_number} from {company_name}",
            _invoice_email_html(invoice, company_name),
        )
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return _json_error(f"Could not send the email: {exc}", 502, "SEND_FAILED")

    invoice.client_email = to_email
    if invoice.status == "draft":
        invoice.status = "sent"
    invoice.sent_at = datetime.now(timezone.utc)

    try:
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return _json_error(f"Sent, but could not update the invoice: {exc}", 500, "UPDATE_FAILED")

    return jsonify({"status": "sent", "invoice": invoice.to_dict()}), 200


@invoices_api_bp.post("/<int:invoice_id>/mark-paid")
@jwt_required()
@require_plan("bookkeeping")
def mark_paid(invoice_id: int):
    """Record payment received outside Stripe (check, ACH, cash)."""
    auth, err = _require_auth()
    if err:
        return err
    invoice = _load_invoice(auth["company_id"], invoice_id)
    if not invoice:
        return _json_error("Invoice not found", 404, "NOT_FOUND")
    if invoice.status == "void":
        return _json_error("This invoice has been voided", 409, "VOIDED")

    data = request.get_json(silent=True) or {}
    try:
        amount = _money(data.get("amount", invoice.total), "Amount")
    except ValueError as exc:
        return _json_error(str(exc), 400, "VALIDATION_ERROR")
    if amount <= 0:
        return _json_error("Payment amount must be greater than zero", 400, "VALIDATION_ERROR")

    _apply_payment(invoice, amount, auth["user_id"])

    try:
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return _json_error(f"Could not update the invoice: {exc}", 500, "UPDATE_FAILED")

    return jsonify({"status": "paid", "invoice": invoice.to_dict()}), 200


@invoices_api_bp.post("/<int:invoice_id>/sync-payment")
@jwt_required()
@require_plan("bookkeeping")
def sync_payment(invoice_id: int):
    """
    Ask Stripe whether the payment link has been paid.

    The Stripe webhook (billing/webhooks.py -> apply_invoice_checkout_payment)
    applies payment automatically once it's configured. This stays as a
    manual fallback — for a company that hasn't set the webhook up yet, or
    for a client who just wants to confirm right now instead of waiting.
    """
    auth, err = _require_auth()
    if err:
        return err
    invoice = _load_invoice(auth["company_id"], invoice_id)
    if not invoice:
        return _json_error("Invoice not found", 404, "NOT_FOUND")
    if invoice.status == "paid":
        return jsonify({"status": "paid", "changed": False, "invoice": invoice.to_dict()}), 200
    if not invoice.stripe_payment_link_id:
        return _json_error(
            "This invoice has no Stripe payment link yet — send it first.",
            400,
            "NO_PAYMENT_LINK",
        )

    stripe = _stripe()
    if stripe is None:
        return _json_error("Stripe is not configured", 503, "STRIPE_NOT_CONFIGURED")

    try:
        sessions = stripe.checkout.Session.list(
            payment_link=invoice.stripe_payment_link_id, limit=10
        )
    except Exception as exc:  # noqa: BLE001
        return _json_error(f"Could not reach Stripe: {exc}", 502, "STRIPE_ERROR")

    for session in (sessions.get("data") or []):
        if session.get("payment_status") == "paid":
            amount_total = session.get("amount_total")
            amount = (
                (Decimal(str(amount_total)) / 100).quantize(TWOPLACES)
                if amount_total is not None
                else invoice.total
            )
            _apply_payment(invoice, amount, auth["user_id"])
            try:
                db.session.commit()
            except Exception as exc:  # noqa: BLE001
                db.session.rollback()
                return _json_error(f"Could not update the invoice: {exc}", 500, "UPDATE_FAILED")
            return jsonify({"status": "paid", "changed": True, "invoice": invoice.to_dict()}), 200

    return jsonify(
        {"status": invoice.status, "changed": False, "invoice": invoice.to_dict()}
    ), 200


@invoices_api_bp.delete("/<int:invoice_id>")
@jwt_required()
@require_plan("bookkeeping")
def delete_invoice(invoice_id: int):
    """Delete a draft outright; anything already sent is voided so the record survives."""
    auth, err = _require_auth()
    if err:
        return err
    invoice = _load_invoice(auth["company_id"], invoice_id)
    if not invoice:
        return _json_error("Invoice not found", 404, "NOT_FOUND")

    try:
        if invoice.status == "draft":
            db.session.delete(invoice)
            outcome = "deleted"
        else:
            # Voiding a paid invoice must take its revenue back out of the books.
            _reverse_invoice_journal(invoice)
            invoice.status = "void"
            outcome = "voided"
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return _json_error(f"Could not remove the invoice: {exc}", 500, "DELETE_FAILED")

    return jsonify({"status": outcome, "id": invoice_id}), 200

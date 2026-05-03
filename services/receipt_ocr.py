# freightpay/services/receipt_ocr.py
# RECEIPT OCR INGESTION (provider-agnostic, posting-ready)

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.receipts import Receipt, ReceiptItem


class OCRProcessingError(Exception):
    pass


def ingest_ocr_result(
    db: Session,
    *,
    receipt_id,
    company_id,
    ocr_payload: dict,
):
    """
    Normalize OCR output into Receipt + ReceiptItems.

    Expected ocr_payload (provider-agnostic):
    {
        "vendor": str,
        "date": "YYYY-MM-DD",
        "subtotal": "12.34",
        "tax": "1.23",
        "tip": "0.00",
        "total": "13.57",
        "currency": "USD",
        "items": [
            {"description": "...", "quantity": 1, "unit_price": "12.34"}
        ]
    }
    """

    receipt = (
        db.execute(
            select(Receipt).where(
                Receipt.id == receipt_id,
                Receipt.company_id == company_id,
            )
        ).scalar_one_or_none()
    )

    if not receipt:
        raise OCRProcessingError("Receipt not found")

    if receipt.status not in ("uploaded", "categorized"):
        raise OCRProcessingError("Receipt cannot accept OCR updates")

    # Header fields
    receipt.vendor = ocr_payload.get("vendor") or receipt.vendor
    receipt.receipt_date = ocr_payload.get("date") or receipt.receipt_date

    receipt.subtotal = Decimal(ocr_payload.get("subtotal", receipt.subtotal))
    receipt.tax = Decimal(ocr_payload.get("tax", receipt.tax))
    receipt.tip = Decimal(ocr_payload.get("tip", receipt.tip))
    receipt.total = Decimal(ocr_payload.get("total", receipt.total))
    receipt.currency = ocr_payload.get("currency", receipt.currency)

    # Clear existing items (OCR overwrite is intentional)
    receipt.items.clear()

    for raw in ocr_payload.get("items", []):
        qty = Decimal(str(raw.get("quantity", "1")))
        unit = Decimal(str(raw.get("unit_price", "0.00")))
        line_total = (qty * unit).quantize(Decimal("0.01"))

        item = ReceiptItem(
            description=raw.get("description", "Item"),
            quantity=qty,
            unit_price=unit,
            line_total=line_total,
        )
        receipt.items.append(item)

    # Mark as categorized if accounts still missing
    if receipt.expense_account_code and receipt.payment_account_code:
        receipt.status = "categorized"

    db.commit()
    return receipt.id

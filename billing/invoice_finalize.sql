-- File: billing/invoice_finalize.sql
-- Purpose: Hardened invoice finalization + lock (PRODUCTION)
-- Guarantees immutability, auditability, and Stripe parity
-- Date: 2026-01-26

BEGIN;

-- =========================
-- INVOICES TABLE (FINALIZE SUPPORT)
-- =========================
CREATE TABLE IF NOT EXISTS invoices (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL,
    customer_id TEXT NOT NULL,
    stripe_invoice_id TEXT,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    subtotal_cents BIGINT NOT NULL DEFAULT 0,
    tax_cents BIGINT NOT NULL DEFAULT 0,
    total_cents BIGINT NOT NULL DEFAULT 0,

    status TEXT NOT NULL DEFAULT 'draft', -- draft | finalized | paid | void
    finalized_at TIMESTAMPTZ,
    finalized_by BIGINT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invoices_company
    ON invoices(company_id);

CREATE INDEX IF NOT EXISTS idx_invoices_customer
    ON invoices(customer_id);

CREATE INDEX IF NOT EXISTS idx_invoices_status
    ON invoices(status);

-- =========================
-- INVOICE LINE ITEMS
-- =========================
CREATE TABLE IF NOT EXISTS invoice_line_items (
    id BIGSERIAL PRIMARY KEY,
    invoice_id BIGINT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price_cents BIGINT NOT NULL,
    amount_cents BIGINT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invoice_line_items_invoice
    ON invoice_line_items(invoice_id);

-- =========================
-- FINALIZATION LOCK (HARD GUARANTEE)
-- =========================
CREATE OR REPLACE FUNCTION prevent_invoice_mutation()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status = 'finalized' THEN
        RAISE EXCEPTION 'Invoice is finalized and cannot be modified';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_lock_finalized_invoice ON invoices;
CREATE TRIGGER trg_lock_finalized_invoice
BEFORE UPDATE ON invoices
FOR EACH ROW
WHEN (OLD.status = 'finalized')
EXECUTE FUNCTION prevent_invoice_mutation();

DROP TRIGGER IF EXISTS trg_lock_finalized_invoice_items ON invoice_line_items;
CREATE TRIGGER trg_lock_finalized_invoice_items
BEFORE UPDATE OR DELETE ON invoice_line_items
FOR EACH ROW
EXECUTE FUNCTION prevent_invoice_mutation();

-- =========================
-- AUDIT LOG (BILLING)
-- =========================
CREATE TABLE IF NOT EXISTS billing_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    invoice_id BIGINT,
    actor_id BIGINT,
    action TEXT NOT NULL, -- finalize | void | pay
    snapshot JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_billing_audit_invoice
    ON billing_audit_logs(invoice_id);

COMMIT;

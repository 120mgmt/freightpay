-- File: billing/invoicing_migrations.sql
-- Purpose: Add accounting-grade billing persistence (invoices, payments, refunds, tax, period close, subscription changes)
-- Status: FULL PRODUCTION — idempotent, PostgreSQL-safe
-- Date: 2026-01-26

BEGIN;

-- =========================
-- INVOICES (system of record)
-- =========================
CREATE TABLE IF NOT EXISTS billing_invoices (
  id BIGSERIAL PRIMARY KEY,
  stripe_invoice_id TEXT UNIQUE,
  stripe_customer_id TEXT,
  company_id INTEGER,
  subscription_id TEXT,
  currency TEXT NOT NULL DEFAULT 'usd',

  status TEXT NOT NULL DEFAULT 'draft', -- draft|open|paid|uncollectible|void
  amount_due BIGINT NOT NULL DEFAULT 0,
  amount_paid BIGINT NOT NULL DEFAULT 0,
  amount_remaining BIGINT NOT NULL DEFAULT 0,

  subtotal BIGINT NOT NULL DEFAULT 0,
  tax BIGINT NOT NULL DEFAULT 0,
  total BIGINT NOT NULL DEFAULT 0,

  period_start BIGINT,
  period_end BIGINT,
  hosted_invoice_url TEXT,
  invoice_pdf TEXT,

  created_at BIGINT NOT NULL,
  updated_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_billing_invoices_company_id ON billing_invoices(company_id);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_stripe_customer_id ON billing_invoices(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_status ON billing_invoices(status);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_period ON billing_invoices(period_start, period_end);


-- =========================
-- INVOICE LINE ITEMS (optional but production-grade)
-- =========================
CREATE TABLE IF NOT EXISTS billing_invoice_lines (
  id BIGSERIAL PRIMARY KEY,
  stripe_invoice_line_id TEXT UNIQUE,
  stripe_invoice_id TEXT,
  stripe_customer_id TEXT,
  company_id INTEGER,

  description TEXT,
  price_id TEXT,
  product_id TEXT,
  quantity BIGINT,
  unit_amount BIGINT,
  amount BIGINT NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'usd',

  period_start BIGINT,
  period_end BIGINT,

  created_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_billing_invoice_lines_invoice ON billing_invoice_lines(stripe_invoice_id);
CREATE INDEX IF NOT EXISTS idx_billing_invoice_lines_company_id ON billing_invoice_lines(company_id);
CREATE INDEX IF NOT EXISTS idx_billing_invoice_lines_customer_id ON billing_invoice_lines(stripe_customer_id);


-- =========================
-- PAYMENTS / CHARGES (ledger)
-- =========================
CREATE TABLE IF NOT EXISTS billing_payments (
  id BIGSERIAL PRIMARY KEY,

  stripe_payment_intent_id TEXT UNIQUE,
  stripe_charge_id TEXT UNIQUE,
  stripe_customer_id TEXT,
  company_id INTEGER,

  stripe_invoice_id TEXT,
  subscription_id TEXT,

  status TEXT NOT NULL DEFAULT 'unknown', -- succeeded|pending|failed|canceled|requires_action|unknown
  currency TEXT NOT NULL DEFAULT 'usd',
  amount BIGINT NOT NULL DEFAULT 0,

  failure_code TEXT,
  failure_message TEXT,

  created_at BIGINT NOT NULL,
  updated_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_billing_payments_company_id ON billing_payments(company_id);
CREATE INDEX IF NOT EXISTS idx_billing_payments_customer_id ON billing_payments(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_billing_payments_invoice_id ON billing_payments(stripe_invoice_id);
CREATE INDEX IF NOT EXISTS idx_billing_payments_status ON billing_payments(status);


-- =========================
-- REFUNDS / CREDITS (post-charge)
-- =========================
CREATE TABLE IF NOT EXISTS billing_refunds (
  id BIGSERIAL PRIMARY KEY,

  stripe_refund_id TEXT UNIQUE,
  stripe_charge_id TEXT,
  stripe_payment_intent_id TEXT,
  stripe_customer_id TEXT,
  company_id INTEGER,

  stripe_invoice_id TEXT,
  currency TEXT NOT NULL DEFAULT 'usd',
  amount BIGINT NOT NULL DEFAULT 0,

  status TEXT NOT NULL DEFAULT 'unknown', -- pending|succeeded|failed|canceled|unknown
  reason TEXT,

  created_at BIGINT NOT NULL,
  updated_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_billing_refunds_company_id ON billing_refunds(company_id);
CREATE INDEX IF NOT EXISTS idx_billing_refunds_customer_id ON billing_refunds(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_billing_refunds_invoice_id ON billing_refunds(stripe_invoice_id);


-- =========================
-- TAX AUDIT LINES (jurisdiction/rate used)
-- =========================
CREATE TABLE IF NOT EXISTS billing_tax_lines (
  id BIGSERIAL PRIMARY KEY,

  stripe_invoice_id TEXT,
  stripe_customer_id TEXT,
  company_id INTEGER,

  jurisdiction TEXT,
  tax_type TEXT,              -- sales_tax|vat|gst|other
  tax_rate_bps INTEGER,       -- basis points (e.g., 825 = 8.25%)
  taxable_amount BIGINT NOT NULL DEFAULT 0,
  tax_amount BIGINT NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'usd',

  created_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_billing_tax_lines_invoice_id ON billing_tax_lines(stripe_invoice_id);
CREATE INDEX IF NOT EXISTS idx_billing_tax_lines_company_id ON billing_tax_lines(company_id);
CREATE INDEX IF NOT EXISTS idx_billing_tax_lines_customer_id ON billing_tax_lines(stripe_customer_id);


-- =========================
-- BILLING PERIOD CLOSE (prevents retroactive mutation)
-- =========================
CREATE TABLE IF NOT EXISTS billing_period_closes (
  id BIGSERIAL PRIMARY KEY,
  company_id INTEGER NOT NULL,

  period_start BIGINT NOT NULL,
  period_end BIGINT NOT NULL,

  closed BOOLEAN NOT NULL DEFAULT FALSE,
  closed_at BIGINT,
  closed_by_user_id INTEGER,

  created_at BIGINT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_billing_period_closes_company_period
  ON billing_period_closes(company_id, period_start, period_end);

CREATE INDEX IF NOT EXISTS idx_billing_period_closes_company_closed
  ON billing_period_closes(company_id, closed);


-- =========================
-- SUBSCRIPTION CHANGE EVENTS (upgrade/downgrade/proration intent)
-- =========================
CREATE TABLE IF NOT EXISTS billing_subscription_changes (
  id BIGSERIAL PRIMARY KEY,

  stripe_event_id TEXT UNIQUE,
  company_id INTEGER,
  stripe_customer_id TEXT,
  subscription_id TEXT,

  change_type TEXT NOT NULL,   -- created|updated|canceled|paused|resumed|upgraded|downgraded
  from_price_ids_json TEXT,    -- JSON array
  to_price_ids_json TEXT,      -- JSON array

  proration_behavior TEXT,     -- create_prorations|none|always_invoice
  proration_amount BIGINT,     -- if known
  effective_at BIGINT,         -- epoch seconds

  created_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_billing_subscription_changes_company_id ON billing_subscription_changes(company_id);
CREATE INDEX IF NOT EXISTS idx_billing_subscription_changes_customer_id ON billing_subscription_changes(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_billing_subscription_changes_subscription_id ON billing_subscription_changes(subscription_id);

COMMIT;

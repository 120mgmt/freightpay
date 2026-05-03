-- File: billing/migrations.sql
-- Purpose: Canonical billing schema migrations (Stripe-aligned, production)
-- Status: FULL PRODUCTION — idempotent, safe on Postgres
-- Date: 2026-01-26

BEGIN;

-- =========================
-- Billing Events (audit / domain)
-- =========================
CREATE TABLE IF NOT EXISTS billing_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    company_id INTEGER,
    customer_id TEXT,
    payload_json TEXT NOT NULL,
    occurred_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_billing_events_company
    ON billing_events(company_id);

CREATE INDEX IF NOT EXISTS idx_billing_events_customer
    ON billing_events(customer_id);

CREATE INDEX IF NOT EXISTS idx_billing_events_type
    ON billing_events(event_type);

CREATE INDEX IF NOT EXISTS idx_billing_events_time
    ON billing_events(occurred_at);


-- =========================
-- Customer Subscriptions (authoritative cache)
-- =========================
CREATE TABLE IF NOT EXISTS customer_subscriptions (
    customer_id TEXT PRIMARY KEY,
    active BOOLEAN NOT NULL,
    status TEXT,
    subscription_id TEXT,
    price_id TEXT,
    price_ids_json TEXT,
    current_period_end BIGINT,
    entitlements_json TEXT,
    updated_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_customer_subscriptions_updated_at
    ON customer_subscriptions(updated_at);

CREATE INDEX IF NOT EXISTS idx_customer_subscriptions_subscription_id
    ON customer_subscriptions(subscription_id);


-- =========================
-- Stripe Webhook Idempotency
-- =========================
CREATE TABLE IF NOT EXISTS stripe_webhook_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT,
    customer_id TEXT,
    company_id INTEGER,
    received_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stripe_webhook_events_customer_id
    ON stripe_webhook_events(customer_id);

CREATE INDEX IF NOT EXISTS idx_stripe_webhook_events_company_id
    ON stripe_webhook_events(company_id);

CREATE INDEX IF NOT EXISTS idx_stripe_webhook_events_received_at
    ON stripe_webhook_events(received_at);


-- =========================
-- Usage Metering (durable counters)
-- =========================
CREATE TABLE IF NOT EXISTS usage_counters (
    company_id INTEGER NOT NULL,
    metric TEXT NOT NULL,
    period_start BIGINT NOT NULL,
    period_end BIGINT NOT NULL,
    used BIGINT NOT NULL DEFAULT 0,
    updated_at BIGINT NOT NULL,
    PRIMARY KEY (company_id, metric, period_start)
);

CREATE INDEX IF NOT EXISTS idx_usage_counters_company_metric
    ON usage_counters(company_id, metric);

CREATE INDEX IF NOT EXISTS idx_usage_counters_period
    ON usage_counters(period_start, period_end);


-- =========================
-- Invoices Cache (read-optimized)
-- =========================
CREATE TABLE IF NOT EXISTS billing_invoices (
    invoice_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    company_id INTEGER,
    status TEXT,
    amount_due BIGINT,
    amount_paid BIGINT,
    currency TEXT,
    hosted_invoice_url TEXT,
    pdf_url TEXT,
    period_start BIGINT,
    period_end BIGINT,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_billing_invoices_company
    ON billing_invoices(company_id);

CREATE INDEX IF NOT EXISTS idx_billing_invoices_customer
    ON billing_invoices(customer_id);

CREATE INDEX IF NOT EXISTS idx_billing_invoices_status
    ON billing_invoices(status);


-- =========================
-- Dunning State
-- =========================
CREATE TABLE IF NOT EXISTS billing_dunning (
    customer_id TEXT PRIMARY KEY,
    company_id INTEGER,
    state TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    next_retry_at BIGINT,
    updated_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_billing_dunning_state
    ON billing_dunning(state);


COMMIT;

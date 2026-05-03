-- File: billing/idempotency.sql
-- Purpose: Durable idempotency enforcement for billing + Stripe-facing operations
-- Scope: Webhooks, checkout, refunds, coupons, invoices, retries
-- Status: FULL PRODUCTION – REQUIRED for sellable SaaS
-- Date: 2026-01-26

BEGIN;

-- =====================================================
-- STRIPE / BILLING IDEMPOTENCY KEYS
-- =====================================================
-- Ensures the same external event or request
-- can NEVER be processed twice (retries safe)

CREATE TABLE IF NOT EXISTS billing_idempotency_keys (
    id BIGSERIAL PRIMARY KEY,

    -- External idempotency key (Stripe event id, request-id, etc.)
    idempotency_key TEXT NOT NULL,

    -- Logical operation scope
    scope TEXT NOT NULL, 
    -- examples:
    --   stripe_webhook
    --   checkout_create
    --   refund_issue
    --   coupon_redeem
    --   invoice_finalize

    -- Optional linkage
    customer_id TEXT,
    company_id INTEGER,

    -- Request fingerprint (defensive)
    request_hash TEXT,

    -- Result snapshot (JSON, optional)
    response_json JSONB,

    -- State
    processed BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

-- =====================================================
-- HARD GUARANTEES
-- =====================================================

-- Absolute uniqueness per scope
CREATE UNIQUE INDEX IF NOT EXISTS ux_billing_idempotency_key_scope
    ON billing_idempotency_keys (idempotency_key, scope);

-- Fast lookup for hot paths
CREATE INDEX IF NOT EXISTS ix_billing_idempotency_key
    ON billing_idempotency_keys (idempotency_key);

CREATE INDEX IF NOT EXISTS ix_billing_idempotency_company
    ON billing_idempotency_keys (company_id);

CREATE INDEX IF NOT EXISTS ix_billing_idempotency_customer
    ON billing_idempotency_keys (customer_id);

CREATE INDEX IF NOT EXISTS ix_billing_idempotency_processed
    ON billing_idempotency_keys (processed);

-- =====================================================
-- SAFETY CONSTRAINT
-- =====================================================
-- processed_at must exist if processed=true

ALTER TABLE billing_idempotency_keys
    ADD CONSTRAINT chk_billing_idempotency_processed_at
    CHECK (
        (processed = FALSE AND processed_at IS NULL)
        OR
        (processed = TRUE AND processed_at IS NOT NULL)
    );

COMMIT;

-- File: billing/reports.sql
-- Purpose: Read-only billing analytics views (MRR, ARR, churn, usage)
-- Status: FULL PRODUCTION — deterministic, no writes, Postgres-safe
-- Date: 2026-01-26

BEGIN;

-- =========================
-- Monthly Recurring Revenue (MRR)
-- =========================
CREATE OR REPLACE VIEW billing_mrr AS
SELECT
    cs.customer_id,
    cs.price_id,
    cs.status,
    cs.active,
    cs.updated_at,
    COALESCE(
        (cs.entitlements_json::jsonb -> 'limits' ->> 'monthly_price')::BIGINT,
        0
    ) AS mrr_amount
FROM customer_subscriptions cs
WHERE cs.active = TRUE;


-- =========================
-- Annual Recurring Revenue (ARR)
-- =========================
CREATE OR REPLACE VIEW billing_arr AS
SELECT
    customer_id,
    (mrr_amount * 12) AS arr_amount
FROM billing_mrr;


-- =========================
-- Active Customers
-- =========================
CREATE OR REPLACE VIEW billing_active_customers AS
SELECT
    customer_id,
    status,
    updated_at
FROM customer_subscriptions
WHERE active = TRUE;


-- =========================
-- Churned Customers
-- =========================
CREATE OR REPLACE VIEW billing_churned_customers AS
SELECT
    customer_id,
    status,
    updated_at
FROM customer_subscriptions
WHERE active = FALSE
  AND status IS NOT NULL;


-- =========================
-- Usage Summary (current period)
-- =========================
CREATE OR REPLACE VIEW billing_usage_summary AS
SELECT
    company_id,
    metric,
    period_start,
    period_end,
    used
FROM usage_counters
WHERE period_end >= EXTRACT(EPOCH FROM NOW())::BIGINT;


COMMIT;

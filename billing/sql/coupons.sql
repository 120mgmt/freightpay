-- File: billing/sql/coupons.sql
-- Purpose: Coupon + discount persistence (production, Stripe-aligned)
-- Status: FULL PRODUCTION – hardened, idempotent, auditable
-- Date: 2026-01-26

BEGIN;

-- =========================
-- Coupons master table
-- =========================
CREATE TABLE IF NOT EXISTS billing_coupons (
    id                BIGSERIAL PRIMARY KEY,
    coupon_code       TEXT NOT NULL UNIQUE,              -- human-readable code
    stripe_coupon_id  TEXT UNIQUE,                        -- optional Stripe coupon id
    stripe_promo_id   TEXT UNIQUE,                        -- optional Stripe promotion code id

    discount_type     TEXT NOT NULL CHECK (discount_type IN ('percent','amount')),
    discount_value    INTEGER NOT NULL CHECK (discount_value >= 0),

    currency          TEXT,                               -- required if amount-based
    duration          TEXT NOT NULL CHECK (duration IN ('once','repeating','forever')),
    duration_months   INTEGER CHECK (duration_months >= 1),

    max_redemptions   INTEGER CHECK (max_redemptions >= 1),
    times_redeemed    INTEGER NOT NULL DEFAULT 0,

    valid_from        TIMESTAMPTZ,
    valid_until       TIMESTAMPTZ,

    active            BOOLEAN NOT NULL DEFAULT TRUE,

    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_billing_coupons_active
    ON billing_coupons (active);

CREATE INDEX IF NOT EXISTS idx_billing_coupons_validity
    ON billing_coupons (valid_from, valid_until);


-- =========================
-- Coupon redemptions (audit)
-- =========================
CREATE TABLE IF NOT EXISTS billing_coupon_redemptions (
    id               BIGSERIAL PRIMARY KEY,
    coupon_id        BIGINT NOT NULL REFERENCES billing_coupons(id) ON DELETE CASCADE,

    customer_id      TEXT,           -- Stripe customer id (cus_)
    company_id       INTEGER,        -- internal company id
    invoice_id       TEXT,           -- Stripe invoice id (in_)
    subscription_id  TEXT,           -- Stripe subscription id (sub_)

    redeemed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_coupon_redemptions_coupon
    ON billing_coupon_redemptions (coupon_id);

CREATE INDEX IF NOT EXISTS idx_coupon_redemptions_customer
    ON billing_coupon_redemptions (customer_id);

CREATE INDEX IF NOT EXISTS idx_coupon_redemptions_company
    ON billing_coupon_redemptions (company_id);


-- =========================
-- Trigger: maintain updated_at
-- =========================
CREATE OR REPLACE FUNCTION billing_coupons_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_billing_coupons_updated_at ON billing_coupons;

CREATE TRIGGER trg_billing_coupons_updated_at
BEFORE UPDATE ON billing_coupons
FOR EACH ROW
EXECUTE FUNCTION billing_coupons_touch_updated_at();

COMMIT;

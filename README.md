# LedgerHaul — Production Backend Service

LedgerHaul is a production backend service for payroll, contractor settlements, and subscription management in the trucking and logistics industry.

Public informational site: https://ledgerhaul.com

---

## Overview

LedgerHaul provides programmatic payroll calculations, contractor settlement logic, billing enforcement, and third-party integrations. The application is API-first and designed to operate as a live backend service supporting paid subscriptions and operational workflows.

---

## Core Capabilities

### Authentication & Authorization
- User registration and login
- Role-based access control (`admin`, `client`, `driver`)
- Session-based authentication
- Route-level permission enforcement

### Database & Persistence
- PostgreSQL (Render) with SQLite fallback for local development
- SQLAlchemy ORM
- Alembic / Flask-Migrate migrations
- Production-safe connection handling

### Billing & Subscriptions (Stripe)
- Subscription billing using environment-driven Stripe Price IDs
- Supported plans:
  - Combo (Payroll + Bookkeeping): base + per-employee
  - Payroll Only: base + per-employee
  - Bookkeeping Only: flat-rate
- Stripe Checkout (subscription mode)
- Webhook handling:
  - `checkout.session.completed`
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.payment_failed`
- Subscription state persisted and enforced via entitlements

### Contractor Payroll Engine
- Per-mile pay (simple and split loaded/empty miles)
- Flat-rate pay
- Percentage-of-revenue pay
- Accessorials (detention, layover, TONU, etc.)
- Deductions (escrow, fuel advances, insurance, admin fees)
- Gross-to-net settlement calculations
- Audit-safe line item tracking

### Gusto Integration
- OAuth connect endpoint
- OAuth callback with token exchange
- Secure token handling
- Demo environment active
- Structured for production payroll scopes pending partner approval

### Entitlements & Access Control
- Active subscription required for feature access
- Plan-aware feature gating
- Automatic restriction on cancellation or payment failure

### Legal & Compliance
- Terms of Service endpoint
- Privacy Policy endpoint
- Refund Policy endpoint
- Structured for third-party review

---

## Architecture

- **Language:** Python 3.12.x
- **Framework:** Flask
- **Payments:** Stripe
- **Payroll Provider:** Gusto API
- **Hosting:** Render
- **Database:** PostgreSQL / SQLite
- **Auth:** OAuth 2.0
- **Webhooks:** Stripe + Gusto
- **Server:** Gunicorn

---

## Environment Variables

Create a `.env` file locally (do not commit secrets):


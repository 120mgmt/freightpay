# FreightPay — Production Trucking Payroll & Settlements Platform

FreightPay is a full-stack production platform for payroll, contractor settlements, double-entry bookkeeping, and Stripe subscription billing — built for trucking and logistics carriers.

---

## Project Structure

```
freightpay/
├── frontend/           # React + Vite + Tailwind + shadcn/ui (landing page & UI)
├── app.py              # Flask application entry point
├── billing/            # Stripe subscriptions, checkout, webhooks, invoicing
├── bookkeeping/        # Double-entry ledger, QuickBooks export
├── compliance/         # Audit trails, legal enforcement, compliance routes
├── config/             # App settings and environment config
├── extensions/         # JWT and Flask extensions
├── integrations/       # Gusto, Check, and payroll provider integrations
├── jobs/               # Background workers and receipt processing
├── legal/              # Terms, privacy, legal acceptance routes
├── middleware/          # RBAC, rate limiting, idempotency, security headers
├── migrations/         # Alembic database migrations
├── models/             # SQLAlchemy ORM models
├── payroll/            # Payroll engine, settlements, deductions, exports
├── repositories/       # Data access layer
├── routes/             # API route handlers
├── services/           # Business logic services
├── templates/          # Jinja2 HTML templates
├── tests/              # Test suite
├── users/              # User management and email verification
└── utils/              # Auth, audit, database, and helper utilities
```

---

## Backend Setup

**Requirements:** Python 3.11+, PostgreSQL (or SQLite for dev)

```bash
pip install -r requirements.txt
flask db upgrade
flask run
```

**Key environment variables:**
```
DATABASE_URL=postgresql://...
SECRET_KEY=...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
JWT_SECRET_KEY=...
```

---

## Frontend Setup

```bash
cd frontend
npm install
npm run dev        # dev server on http://localhost:8080
npm run build      # production build
```

---

## Core Features

- **Payroll Engine** — per-mile, per-load, percentage, and salary pay models
- **Contractor Settlements** — fuel advances, IFTA, escrow, insurance deductions
- **Double-Entry Bookkeeping** — every transaction posts balanced ledger entries
- **Stripe Billing** — Combo, Payroll Only, Bookkeeping Only subscription plans
- **JWT Auth + RBAC** — admin, client, and driver roles
- **1099-NEC / W-2 Export** — year-round tax form generation
- **Webhook Event Stream** — settlement state changes, billing events
- **Audit Trail** — immutable history for every financial operation

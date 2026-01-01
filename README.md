# FreightPay – Full Production Deployment (v5)

FreightPay is a **production-grade SaaS platform** for trucking and logistics operators.  
This repository is **not an MVP, not a demo, and not a skeleton**. It is structured for **live users, paid subscriptions, and production operations**.

---

## Platform Capabilities (Production)

### Authentication & Authorization
- User registration, login, logout
- Role-based access control: `admin`, `client`, `driver`
- Session-based authentication and JWT support
- Enforced permissions at route and service level

### Database & Persistence
- PostgreSQL (Render) with SQLite fallback for local development
- SQLAlchemy ORM
- Alembic / Flask-Migrate migrations
- Seeded baseline data
- Production-safe connection handling

### Billing & Subscriptions (Stripe – Live Mode)
- Subscription billing using **Stripe Price IDs (environment-driven)**
- Supported plans:
  - **Combo** (Payroll + Bookkeeping): base + per-employee
  - **Payroll Only**: base + per-employee
  - **Bookkeeping Only**: flat-rate
- Stripe Checkout (subscription mode)
- Webhook handling:
  - `checkout.session.completed`
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.payment_failed`
- Subscription state persisted and enforced via entitlements

### Gusto Integration
- OAuth connect endpoint
- OAuth callback with token exchange
- Secure token storage in database
- Structured for production payroll scopes (partner approval required)

### Entitlements & Access Control
- Active subscription required for feature access
- Plan-aware feature gating
- Automatic restriction on cancellation or payment failure

### Legal & Compliance
- Terms of Service endpoint
- Privacy Policy endpoint
- Refund Policy endpoint
- Designed for production compliance and third-party review

### User Interface
- Server-rendered UI (Jinja templates)
- Home, login, register
- Client dashboard
- Admin dashboard
- Billing-aware UI states

### Deployment & Runtime
- Python **3.12.1**
- Gunicorn application server
- Render-compatible
- 12-factor, environment-variable–driven configuration

---

## What This Repository Is NOT
- Not an MVP
- Not a prototype
- Not a demo
- Not hardcoded pricing or secrets
- Not missing core infrastructure

---

## Local Setup (Production-Equivalent)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
flask --app freightpay:create_app db upgrade
flask --app freightpay:create_app seed
flask --app freightpay:create_app run

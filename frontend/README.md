# FreightPay

Production backend and frontend for trucking payroll, contractor settlements, double-entry bookkeeping, and Stripe subscription billing.

## Structure

```
freightpay/
├── backend/        # Python Flask API (payroll, settlements, billing, bookkeeping)
└── src/            # React + Vite frontend (landing page & dashboard UI)
```

## Backend

Flask API with PostgreSQL, JWT auth, Stripe billing, and double-entry bookkeeping.

```bash
cd backend
pip install -r requirements.txt
flask db upgrade
flask run
```

## Frontend

React + Vite + Tailwind + shadcn/ui landing page.

```bash
npm install
npm run dev
```

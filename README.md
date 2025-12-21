# FreightPay Full MVP Code (Foundation)

This repo is a functioning MVP baseline (not a single-file skeleton):
- Auth (register/login/logout) with Flask-Login
- Roles: admin/client/driver
- Postgres/SQLite via SQLAlchemy
- Migrations included (Alembic + Flask-Migrate)
- UI (Jinja templates): home/login/register/dashboard/admin
- Gusto OAuth: /oauth/gusto/connect and /oauth/gusto/callback (token exchange + DB save)
- Stripe billing stub: /billing (checkout + webhook endpoint)

## Local setup
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
flask --app freightpay:create_app db upgrade
flask --app freightpay:create_app seed
flask --app freightpay:create_app run
```

Visit http://127.0.0.1:5000

## Render
- Build Command:
  `pip install -r requirements.txt && flask --app freightpay:create_app db upgrade`
- Start Command:
  `gunicorn wsgi:app`
- Add env vars shown in `.env.example`.

## Important
This is an MVP foundation. It is not a complete payroll product yet (you still need full payroll logic, client onboarding flows,
accounting rules, permissions, audit logs, etc.). But it is a real running app with auth + DB + UI + OAuth wiring.

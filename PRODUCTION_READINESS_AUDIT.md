# Production Readiness Audit — FreightPay/LedgerHaul

**Date:** 2026-03-14  
**Scope:** Full repo (app entry, config, migrations, billing, payroll, legal/compliance, bookkeeping, integrations)

---

## Priority 1 — Must fix before production (blockers)

### 1.1 Broken imports (wrong package name `freightpay.`)

The codebase uses `freightpay.models.*` and `freightpay.services.*` but the project runs as a flat layout (no top-level `freightpay` package). These imports will raise `ModuleNotFoundError` at runtime when those code paths run.

| File | Fix |
|------|-----|
| **`services/receipt_ocr.py`** | Change `from freightpay.models.receipts import Receipt, ReceiptItem` → `from models.receipts import Receipt, ReceiptItem` |
| **`services/ledger_posting_guard.py`** | Change `from freightpay.models.accounting_periods` → `from models.periods` (or `models.accounting_periods` if that module is the one used by the app). Change `from freightpay.models.ledger` → `from models.ledger`. Align `AccountingPeriod` and `Journal`/`LedgerEntry` with the actual models (see 1.2). |
| **`services/bank_transaction_posting.py`** | Change `from freightpay.models.bank_accounts` → `from models.bank_accounts`, `from freightpay.models.categorization_rules` → `from models.categorization_rules`, `from freightpay.services.ledger_posting_guard` → `from services.ledger_posting_guard` |
| **`routes/contractor_payroll.py`** | Change `from freightpay.models.payroll import ...` → `from models.payroll import ...` (and ensure `utils.database.Base` is the same as app’s db/metadata). |
| **`repositories/payroll_repository.py`** | Change `from freightpay.models.payroll import ...` → `from models.payroll import ...`. Confirm that `PayrollAccessorial`, `PayrollDeduction` exist in `models/payroll.py` or remove from import. |
| **`routes/admin_payroll.py`** | Change `from freightpay.repositories.payroll_repository import ...` → `from repositories.payroll_repository import ...`. Register this blueprint in `app.py` if it is intended to be used. |

### 1.2 Missing or inconsistent model exports

| File | Issue | Fix |
|------|--------|-----|
| **`models/__init__.py`** | Exports only `Company`, `User`, `RefreshToken`. Does not export `AccountingPeriod`, `Journal`, `JournalLine`, `ChartOfAccount`/`Account`. | Add exports for all models used by `services/journal_posting.py`, `services/reconciliation.py`, and `services/period_management.py`, or change those services to import from concrete modules (e.g. `models.ledger`, `models.periods`, `models.chart_of_accounts`). |
| **`services/journal_posting.py`** | Imports `from models import AccountingPeriod, ChartOfAccount, Journal, JournalLine`. `ChartOfAccount` does not exist; `models/chart_of_accounts.py` defines `Account`. | Either add `ChartOfAccount = Account` (or alias) in `models/chart_of_accounts.py` and export from `models/__init__.py`, or change `journal_posting` to use `Account` and import from `models.periods`, `models.chart_of_accounts`, `models.ledger`, `models.general_ledger` (or wherever `Journal`/`JournalLine` live). |
| **`models/accounting_periods.py`** | Uses `from .base import Base` and UUID; **`models/periods.py`** uses `db.Model` and Integer. Two different period models. | Decide single source of truth. Migrations and `models/ledger.py` use Integer and Flask-SQLAlchemy; align `services/ledger_posting_guard.py` and reconciliation with the same model set (likely `models/periods.py` and `models/ledger.py`). |

### 1.3 Legal seed broken

| File | Issue | Fix |
|------|--------|-----|
| **`legal/seed.py`** | Imports `CURRENT_TERMS_VERSION`, `CURRENT_PRIVACY_VERSION`, `CURRENT_REFUND_VERSION` from `legal.service`, but **`legal/service.py` does not define or export these**. | Either define and export these constants in `legal/service.py` (and implement seed logic that creates `LegalVersion` rows if missing), or remove the seed and document that legal versions must be created via another path (e.g. admin or migration). |

### 1.4 Receipts flow depends on broken modules

| File | Issue | Fix |
|------|--------|-----|
| **`routes/receipts.py`** | Uses `__import__("services.receipt_ocr", ...)` and `__import__("services.receipt_journalization", ...)`. When those run, `receipt_ocr` uses `freightpay.models.receipts` and `receipt_journalization` uses `from services.ledger_posting_guard import post_journal`; `ledger_posting_guard` uses `freightpay.models.*`. | After fixing 1.1 and 1.2, the dynamic imports should work. Optionally replace `__import__` with normal imports. |

---

## Priority 2 — Migration and config (high impact)

### 2.1 Alembic / Flask-Migrate split

| Item | Issue | Fix |
|------|--------|-----|
| **Root `alembic.ini`** | `script_location = temp_alembic` and `sqlalchemy.url = postgresql://...` (or placeholder). **`temp_alembic/`** has its own `env.py` (no Flask); **`migrations/`** has Flask-Migrate `env.py` and the real revision chain. | Use a single migration path. For the app, use **Flask-Migrate**: `flask db upgrade` (and ensure `migrations/alembic.ini` or app config is used). Remove or repurpose root `alembic.ini` so it does not point at `temp_alembic` for production, or document that production must run `flask db upgrade` from the app context. |
| **`migrations/alembic.ini`** | Contains placeholder `sqlalchemy.url = driver://user:pass@localhost/dbname`. | Flask-Migrate ignores this when run with app context; ensure Render/production runs migrations via `flask db upgrade` (or equivalent) so the app’s `DATABASE_URL` is used. Document in deploy docs. |
| **`.env` / `.env.example`** | No `.env.example` in repo. | Add `.env.example` listing required variables: `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `BASE_URL`, `CORS_ORIGINS`, `LOG_LEVEL`, etc. |

### 2.2 Migration 20260308 — PostgreSQL enum and downgrade

| File | Issue | Fix |
|------|--------|-----|
| **`migrations/versions/20260308_tenant_coa_tables.py`** | In `_ensure_pg_enum`, the bound parameter `:name` is used inside the dynamic `EXECUTE` string. Some drivers may not substitute it correctly inside the nested PL/pgSQL. | Prefer building the enum name into the SQL (with strict validation/allowlist) so the executed string does not rely on parameter substitution inside `EXECUTE`, or test `alembic upgrade` on a real Postgres DB. |
| **Same file** | `downgrade()` drops enums with `sa.Enum(...).drop(bind, checkfirst=True)` but does not pass the PostgreSQL enum name in a way that works for all dialects. | Verify downgrade on Postgres (and that enums are dropped only if no tables reference them). |

### 2.3 Duplicate migration heads / ordering

| Item | Issue | Fix |
|------|--------|-----|
| **20260222 vs 20260308** | Both list `down_revision = "20260216_users_email_verified"`, creating two heads until **20260312_merge_accounting_heads** merges them. | Ensure deployment runs the full chain including the merge revision. Document that fresh installs must run all migrations in order. |

---

## Priority 3 — Billing / payroll integration and consistency

### 3.1 Subscription gating

| Item | Issue | Fix |
|------|--------|-----|
| **Two subscription gates** | **`app.py`** uses `utils.subscription_guard.enforce_subscription_active` (global `before_request`). **`payroll/routes/payroll_routes.py`** and **`routes/driver_settlement_routes.py`** use `billing.subscription_gate.require_active_subscription` (per-route decorator). | Document intended behavior. Ensure both paths use the same notion of “active subscription” (e.g. same company fields or Stripe state) so payroll and driver settlement cannot be accessed without billing when the global guard is intended. |

### 3.2 Unregistered blueprints

| File | Issue | Fix |
|------|--------|-----|
| **`routes/admin_payroll.py`** | Imports `freightpay.repositories.payroll_repository`; not registered in **`app.py`**. | Fix imports (1.1) and, if this admin API is required, register the blueprint in `app.py`. |
| **`routes/contractor_payroll.py`** | Uses `freightpay.models.payroll`; not registered in **`app.py`**. | Fix imports; register in `app.py` if the feature is in scope. |
| **`routes/driver_settlement_routes.py`** | Uses `billing.subscription_gate`; not registered in **`app.py`**. | Register in `app.py` if driver settlement API is in scope. |
| **`routes/demo_routes.py`** | Not registered in **`app.py`**. | Register if needed for demos; otherwise remove or gate behind a feature flag. |

### 3.3 Payroll engine and DB

| File | Issue | Fix |
|------|--------|-----|
| **`payroll/routes/payroll_routes.py`** | Defines `_init_db()` that runs raw DDL for `payroll_runs` table. This bypasses Alembic and can drift from migrations. | Prefer defining `payroll_runs` (and related tables) in a migration and removing ad-hoc DDL from the route, or document that this table is app-managed and not in the main migration chain. |

---

## Priority 4 — Placeholder / silent failure behavior

### 4.1 Routes that swallow errors

| File | Issue | Fix |
|------|--------|-----|
| **`routes/receipts.py`** | Multiple `except Exception: pass` blocks (e.g. around audit logging and fallbacks). Errors are silently ignored. | Replace with at least logging (`logger.exception(...)`) and, where appropriate, return a clear error response instead of `pass`. |
| **`utils/subscription_guard.py`** | In `_company_subscription_is_active`, an exception on `getattr(company, attr)` is caught with `except Exception: pass`, so invalid state can be treated as “unknown” and allow access. | Log the exception and keep fail-open only where explicitly intended; otherwise fail closed or return a defined value. |

### 4.2 Bookkeeping / accounting export

| File | Issue | Fix |
|------|--------|-----|
| **`bookkeeping/accounting_export.py`** | Contains example/placeholder URL comment (`https://api.example.com/journal-entries`). | Replace with real config (e.g. from env or settings) or remove if not used. |

---

## Priority 5 — Legal and compliance gaps

### 5.1 Legal acceptance at runtime

| Item | Issue | Fix |
|------|--------|-----|
| **Legal versions** | **`legal/service.py`** requires active `LegalVersion` rows for terms, privacy, and refund. If none exist (e.g. seed not run or DB reset), `get_required_versions` returns `None` and users cannot complete acceptance. | Implement and run a seed or migration that creates initial `LegalVersion` rows (and optionally link to templates). Fix **legal/seed.py** (1.3) so deployment has a clear, runnable step. |
| **Compliance routes** | **`app.py`** registers `compliance_bp`, `compliance_health_bp`, `admin_compliance_bp`. Ensure these require auth and correct roles where applicable. | Review compliance routes for authz and audit logging. |

### 5.2 Audit logging

| File | Issue | Fix |
|------|--------|-----|
| **`routes/receipts.py`** | `_audit()` tries several model import paths and, if no model is found, logs to app logger and returns. No guarantee that an audit record is persisted. | Either ensure a single `AuditLog` (or equivalent) model is always used and imported, or document that receipt audit is best-effort and add monitoring for audit failures. |

---

## Priority 6 — Environment and deployment

### 6.1 Config and URLs

| Item | Issue | Fix |
|------|--------|-----|
| **`config/settings.py`** and **`config/__init__.py`** | Rely on `os.getenv()`. No validation that required keys are set in production. | Add a startup check (or use a schema) that required env vars are present and non-empty in production; fail fast with a clear message. |
| **Root `alembic.ini`** | Contains a literal DB URL (e.g. `postgresql://postgres:postgres@localhost:5432/freightpay`). | Do not rely on this for production. Prefer `flask db upgrade` with `DATABASE_URL` from the environment. |

### 6.2 Stripe

| Item | Issue | Fix |
|------|--------|-----|
| **`app.py`** | If `STRIPE_SECRET_KEY` is unset, app still starts with a warning; billing endpoints may then fail at runtime. | Document that billing is optional at start; ensure health or readiness checks reflect “billing configured” vs “billing not configured” if needed for operations. |

---

## Summary — Fix order

1. **First:** Fix all **Priority 1** import and model issues so that app and background paths can import and run without `ModuleNotFoundError`. Then fix **legal/seed.py** so legal versions can be seeded.
2. **Second:** Unify migration usage (Flask-Migrate vs root alembic), add `.env.example`, and verify migration 20260308 on Postgres.
3. **Third:** Align subscription gating (global vs decorator), register any required blueprints (admin_payroll, driver_settlement, etc.), and move payroll table definition into migrations if desired.
4. **Fourth:** Replace silent `pass` with logging and explicit error handling in receipts and subscription guard; tighten audit and compliance where needed.
5. **Fifth:** Add env validation and document Stripe and legal/compliance expectations for production.

---

## File reference — quick list of files to change

| Priority | Path |
|----------|------|
| P1 | `services/receipt_ocr.py`, `services/ledger_posting_guard.py`, `services/bank_transaction_posting.py`, `routes/contractor_payroll.py`, `repositories/payroll_repository.py`, `routes/admin_payroll.py`, `models/__init__.py`, `services/journal_posting.py`, `legal/seed.py`, `legal/service.py` (add exports or seed logic) |
| P2 | Root `alembic.ini`, `migrations/alembic.ini`, `migrations/versions/20260308_tenant_coa_tables.py`, add `.env.example` |
| P3 | `app.py` (register blueprints; document subscription guard), `payroll/routes/payroll_routes.py` (DDL vs migrations) |
| P4 | `routes/receipts.py`, `utils/subscription_guard.py`, `bookkeeping/accounting_export.py` |
| P5 | Legal seed/migration for `LegalVersion`, compliance route authz |
| P6 | `config/settings.py` or startup (env validation), deploy docs |

# File: app.py
# Purpose: LedgerHaul API entrypoint
# Purpose: Render-safe, Stripe + JWT + DB + Blueprints
# Purpose: Subscription Guard + Payroll Audit
# Status: Production-ready (Hardened + UX-safe guards)
# Date: 2026-02-23

import logging
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import env_bootstrap  # noqa: F401  # MUST be first: applies DB-stored env overrides before blueprint imports validate env vars

import stripe
from dotenv import load_dotenv
from flask import Flask, jsonify, make_response, request
from flask_cors import CORS
from flask_migrate import Migrate

from billing.checkout import billing_bp
from billing.customer_portal import portal_bp
from billing.customers import customer_bp
from billing.webhooks import webhook_bp
from compliance.admin_routes import admin_compliance_bp
from compliance.health import compliance_health_bp
from compliance.routes import compliance_bp
from db import db, init_db
from legal import register_legal
from jwt_config import init_jwt
from payroll.audit_routes import payroll_audit_bp
from payroll.routes import payroll_bp, provider_submit_bp
from routes.admin_pricing_cpm import admin_pricing_cpm_bp
from routes.auth_routes import auth_bp
from routes.company_routes import company_bp
from routes.pricing_cpm import pricing_cpm_bp
from routes.receipts import receipts_bp
from routes.reconciliation import reconciliation_bp
from routes.reporting import reporting_bp
from routes.contractor import contractor_bp
from routes.tax_1099 import tax_1099_bp
# from routes.driver_settlement_routes import driver_settlement_bp
from routes.bank_connections import bank_connections_bp
from routes.coa import coa_bp
from routes.demo_routes import demo_bp
from users.email_verification import email_verify_bp
from users.routes import users_bp
from app_factory_cli import register_app_cli
from utils.legal_guard import enforce_legal_acceptance
from utils.subscription_guard import enforce_subscription_active

# =========================
# LOAD ENV
# =========================
load_dotenv()

# =========================
# LOGGING
# =========================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("ledgerhaul")

# =========================
# DATABASE URL CHECK (production requires DATABASE_URL; dev/local may use default)
# =========================
APP_ENV_FOR_DB = os.getenv("APP_ENV", "production").strip().lower()
_is_production = APP_ENV_FOR_DB == "production" or os.getenv("RENDER") == "true"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    if _is_production:
        raise RuntimeError("DATABASE_URL is required in production (set APP_ENV=development or set DATABASE_URL)")
    DATABASE_URL = "sqlite:///freightpay.db"
    os.environ["DATABASE_URL"] = DATABASE_URL
    logger.info("DATABASE_URL not set; using default sqlite for local/dev")
logger.info("DATABASE_URL_PRESENT=%s", bool(DATABASE_URL))

try:
    u = urlsplit(DATABASE_URL)
    netloc = u.netloc
    if "@" in netloc and ":" in netloc.split("@")[0]:
        userinfo, hostinfo = netloc.split("@", 1)
        user = userinfo.split(":", 1)[0]
        netloc = f"{user}:****@{hostinfo}"

    if u.scheme.startswith("sqlite") and u.netloc == "":
        masked = f"{u.scheme}:///{u.path.lstrip('/')}"
    else:
        masked = urlunsplit((u.scheme, netloc, u.path, u.query, u.fragment))

    logger.info("DATABASE_URL_VALUE_MASKED=%s", masked)
except Exception:
    logger.info("DATABASE_URL_VALUE_MASKED=(mask failed)")

# =========================
# APP INIT
# =========================
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# =========================
# JWT INIT
# =========================
init_jwt(app)

# =========================
# ENV VARS
# =========================
APP_ENV = os.getenv("APP_ENV", "production").strip().lower()
BASE_URL = (os.getenv("BASE_URL") or "https://ledgerhaul.com").rstrip("/")

# Stripe (allow boot without billing configured so core product can run)
STRIPE_SECRET_KEY = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
STRIPE_WEBHOOK_SECRET = (os.getenv("STRIPE_WEBHOOK_SECRET") or "").strip()

if STRIPE_SECRET_KEY:
    if not (
        STRIPE_SECRET_KEY.startswith("sk_live_")
        or STRIPE_SECRET_KEY.startswith("sk_test_")
    ):
        raise RuntimeError("Invalid STRIPE_SECRET_KEY format")
    stripe.api_key = STRIPE_SECRET_KEY
else:
    if _is_production:
        raise RuntimeError(
            "STRIPE_SECRET_KEY is required in production. "
            "Set it in Render dashboard environment variables."
        )
    logger.warning(
        "STRIPE_SECRET_KEY is not set "
        "(billing endpoints will fail — set before going live)"
    )

if not STRIPE_WEBHOOK_SECRET:
    if _is_production:
        raise RuntimeError(
            "STRIPE_WEBHOOK_SECRET is required in production. "
            "Without it, webhook signature verification will fail and "
            "attackers can forge Stripe events."
        )
    logger.warning(
        "STRIPE_WEBHOOK_SECRET is not set "
        "(webhook verification will fail — set before going live)"
    )

# =========================
# CORS
# =========================
cors_origins_raw = (os.getenv("CORS_ORIGINS") or "").strip()
if cors_origins_raw:
    allowed_origins = [
        origin.strip().rstrip("/")
        for origin in cors_origins_raw.split(",")
        if origin.strip()
    ]
else:
    allowed_origins = [BASE_URL]
    if BASE_URL.startswith("https://") and "://www." not in BASE_URL:
        allowed_origins.append(BASE_URL.replace("https://", "https://www.", 1))

# Always allow Vercel preview URLs (pattern match).
# NOTE: flask-cors accepts strings and compiled regex patterns in the
# origins list — a callable is NOT supported and crashes every request.
_VERCEL_RE = re.compile(r"^https://[a-z0-9-]+-[a-z0-9]+-projects\.vercel\.app$")

CORS(
    app,
    resources={r"/*": {"origins": [*allowed_origins, _VERCEL_RE]}},
    supports_credentials=True,
)

# =========================
# JSON ERROR HANDLERS
# (uncaught exceptions and 404s otherwise return Flask's default HTML
#  page, which breaks every frontend fetch().json() call and shows as a
#  generic "network error" no matter what actually went wrong)
# =========================
@app.errorhandler(404)
def _not_found(_e):
    return jsonify({"error": "not_found"}), 404


@app.errorhandler(Exception)
def _unhandled_exception(e):
    from werkzeug.exceptions import HTTPException

    if isinstance(e, HTTPException):
        return jsonify({"error": e.name.lower().replace(" ", "_"), "message": e.description}), e.code

    logger.exception("Unhandled exception")
    detail = str(e) if APP_ENV != "production" else None
    payload = {"error": "internal_server_error", "message": "Something went wrong. Please try again."}
    if detail:
        payload["detail"] = detail
    return jsonify(payload), 500


# =========================
# SECURITY HEADERS
# =========================
@app.after_request
def add_security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "frame-ancestors 'none'; base-uri 'none';",
    )
    if APP_ENV == "production":
        resp.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
    return resp


# =========================
# HELPERS
# =========================
def _utc_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _path_is_public(p: str) -> bool:
    """
    Public paths must remain accessible even before:
    - legal acceptance
    - subscription activation
    - email verification
    so onboarding/auth + legal pages don't dead-end.
    """
    if not p:
        return True

    if p == "/":
        return True

    allow_prefixes = (
        "/health",
        "/db/ping",
        "/static/",
        "/legal/",
        "/compliance/health",
        "/billing/webhooks/stripe",
        "/billing/webhooks/health",
        "/billing/health",
        "/billing/customers/health",
        "/billing/portal/health",
        "/companies/health",
        "/files/receipts/health",
        "/payroll/health",
        "/payroll/audit/health",
        "/pricing/cpm/",
        "/admin/pricing/cpm/",
        "/auth/login",
        "/auth/register",
        "/auth/signup",
        "/users/login",
        "/users/register",
        "/verify/",
        "/auth/legal/accept",
        "/compliance/legal/accept",
        "/compliance/legal/active",
        "/compliance/legal/status",
    )

    return any(p.startswith(prefix) for prefix in allow_prefixes)


# =========================
# GLOBAL ENFORCEMENT LAYERS
# =========================
@app.before_request
def _legal_guard():
    if _path_is_public(request.path):
        return None
    return enforce_legal_acceptance()


@app.before_request
def _subscription_guard():
    if _path_is_public(request.path):
        return None
    return enforce_subscription_active()


# =========================
# DATABASE INIT
# =========================
init_db(app)
migrate = Migrate(app, db)

# Apply migrations at boot so the schema is always current even when the
# platform start command doesn't run "flask db upgrade". A single attempt
# only — failures are logged, not fatal, and NEVER trigger an automatic
# alembic_version reset. Earlier revisions in this chain (predating this
# repo's idempotency conventions) are not all safe to replay against a
# database that already has their effects applied; a reset-and-retry loop
# here previously wiped alembic_version and got permanently stuck retrying
# a migration that fails with "relation already exists" on every boot,
# which is worse than doing nothing. If migrations are ever genuinely out
# of sync, reconcile deliberately (via a one-off script), not automatically.
if (os.getenv("RUN_MIGRATIONS_ON_BOOT") or "1").strip().lower() in {"1", "true", "yes"}:
    try:
        # NOTE: flask_migrate.upgrade() is wrapped in @catch_errors, which
        # calls sys.exit(1) on failure — that would kill the whole boot (and
        # every platform deploy). We call the alembic command API directly,
        # which raises normal exceptions, and additionally catch SystemExit.
        from alembic import command as _alembic_command

        with app.app_context():
            _alembic_cfg = app.extensions["migrate"].migrate.get_config()
            _alembic_command.upgrade(_alembic_cfg, "head")
        logger.info("DB migrations applied at boot")
    except (Exception, SystemExit) as _mig_err:
        logger.error("DB migration attempt failed (continuing): %s", _mig_err)

# =========================
# REGISTER BLUEPRINTS
# =========================
app.register_blueprint(reporting_bp)
app.register_blueprint(reconciliation_bp)

app.register_blueprint(company_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(users_bp)
app.register_blueprint(email_verify_bp)

# Payroll
app.register_blueprint(payroll_bp)
app.register_blueprint(provider_submit_bp)
app.register_blueprint(payroll_audit_bp)

# Billing
app.register_blueprint(customer_bp)
app.register_blueprint(billing_bp)
app.register_blueprint(portal_bp)
app.register_blueprint(webhook_bp)

# Files
app.register_blueprint(receipts_bp)

# Contractor
app.register_blueprint(contractor_bp)

# 1099
app.register_blueprint(tax_1099_bp)

# Legal
register_legal(app)

# Compliance
app.register_blueprint(compliance_bp)
app.register_blueprint(compliance_health_bp)
app.register_blueprint(admin_compliance_bp)

# Platform admin portal (gated by PLATFORM_ADMIN_EMAILS)
from routes.admin_portal import admin_portal_bp  # noqa: E402
app.register_blueprint(admin_portal_bp)

# Pricing
app.register_blueprint(pricing_cpm_bp)
app.register_blueprint(admin_pricing_cpm_bp)

# Driver settlements
# app.register_blueprint(driver_settlement_bp)

# Bank connections
app.register_blueprint(bank_connections_bp)

# Chart of accounts
app.register_blueprint(coa_bp)

# Demo (no DB writes, marketing safe)
app.register_blueprint(demo_bp)

# CLI
register_app_cli(app)

# =========================
# AUTH ALIAS
# =========================
@app.route("/auth/signup", methods=["OPTIONS"])
def auth_signup_options():
    return ("", 204)


@app.route("/auth/signup", methods=["POST"])
def auth_signup_alias():
    return app.view_functions["auth.register"]()


# =========================
# HEALTH
# =========================
@app.route("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "env": APP_ENV,
            "timestamp": _utc_iso(),
        }
    ), 200


@app.route("/db/ping")
def db_ping():
    try:
        with db.engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return jsonify({"db": "ok"}), 200
    except Exception as e:
        return jsonify({"db": "error", "detail": str(e)}), 500


# =========================
# ROOT
# =========================
@app.route("/")
def index():
    return jsonify(
        {
            "app": "LedgerHaul",
            "status": "live",
            "base_url": BASE_URL,
            "timestamp": _utc_iso(),
        }
    ), 200


# =========================
# LOCAL RUN
# =========================
if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

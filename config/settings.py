# config/settings.py
# Purpose: Production configuration (Render-safe, deployment)
# Status: Full deployment – production v5
# Date: 2026-01-01

import os

# =========================
# Core App
# =========================
ENV = os.getenv("APP_ENV", "production")
DEBUG = ENV != "production"
# SECRET_KEY must be set in environment — no insecure default in production
_raw_secret = os.getenv("SECRET_KEY", "").strip()
if not _raw_secret and os.getenv("APP_ENV", "production") == "production":
    raise RuntimeError(
        "SECRET_KEY is required in production. "
        "Set a long random value in Render dashboard environment variables."
    )
SECRET_KEY = _raw_secret or "dev-only-insecure-key-do-not-use-in-production"

# =========================
# Server
# =========================
PORT = int(os.getenv("PORT", "10000"))

# =========================
# Database
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")
SQLALCHEMY_DATABASE_URI = DATABASE_URL
SQLALCHEMY_TRACK_MODIFICATIONS = False

# =========================
# Security / Auth
# =========================
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# =========================
# Stripe
# =========================
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# =========================
# CORS
# =========================
CORS_ALLOW_HEADERS = ["Content-Type", "Authorization"]
CORS_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

# =========================
# Logging
# =========================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


# =========================
# Production startup validation
# =========================
def validate_production_config() -> None:
    """
    Call at app startup in production.
    Raises RuntimeError immediately if required env vars are missing.
    """
    if ENV != "production":
        return

    required = {
        "DATABASE_URL": os.getenv("DATABASE_URL"),
        "JWT_SECRET_KEY": os.getenv("JWT_SECRET_KEY"),
        "SECRET_KEY": os.getenv("SECRET_KEY"),
        "STRIPE_SECRET_KEY": os.getenv("STRIPE_SECRET_KEY"),
        "STRIPE_WEBHOOK_SECRET": os.getenv("STRIPE_WEBHOOK_SECRET"),
    }

    missing = [k for k, v in required.items() if not v or v.strip() == ""]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables for production: {', '.join(missing)}"
        )

    # Warn on optional but important vars
    import logging
    _log = logging.getLogger("ledgerhaul.config")
    optional = {
        "BASE_URL": os.getenv("BASE_URL"),
        "CORS_ORIGINS": os.getenv("CORS_ORIGINS"),
        "LOG_LEVEL": os.getenv("LOG_LEVEL"),
    }
    for k, v in optional.items():
        if not v:
            _log.warning("Optional env var %s is not set", k)
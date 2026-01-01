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
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-render")

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

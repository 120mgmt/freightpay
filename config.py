# config.py
# FULL, PRODUCTION-READY CONFIG (Render-safe)

from __future__ import annotations
import os


class BaseConfig:
    # Environment
    ENV = os.getenv("ENV", "production")

    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    JSON_SORT_KEYS = False

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")

    # Stripe
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

    # Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = True

    DEBUG = False


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(BaseConfig):
    DEBUG = False


def get_config():
    if BaseConfig.ENV == "production":
        return ProductionConfig()
    return DevelopmentConfig()

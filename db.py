# db.py
# FULL, PRODUCTION-READY DATABASE INITIALIZATION
# Render + Gunicorn safe, Flask-SQLAlchemy + Flask-Migrate

from __future__ import annotations

import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Singletons (imported everywhere)
db = SQLAlchemy()
migrate = Migrate()


def _normalize_database_url(database_url: str) -> str:
    """
    Normalize DATABASE_URL for SQLAlchemy + Render.
    - Fix legacy postgres://
    - Enforce sslmode=require for Render Postgres
    """
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    # Ensure SSL for Render Postgres
    if "sslmode=" not in database_url:
        sep = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{sep}sslmode=require"

    return database_url


def init_db(app):
    """
    Initialize database and migrations.
    Call ONCE during app startup.
    """

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required")

    database_url = _normalize_database_url(database_url)

    app.config.update(
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
        },
    )

    db.init_app(app)
    migrate.init_app(app, db)

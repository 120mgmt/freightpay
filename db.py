# db.py
# FULL, PRODUCTION-READY DATABASE INITIALIZATION (Render + Python 3.13)
# Forces SQLAlchemy to use psycopg (v3) driver.

from __future__ import annotations

import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()


def _normalize_database_url(database_url: str) -> str:
    # legacy "postgres://" fix
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    # FORCE psycopg3 driver (this is the key fix)
    if database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]
    elif database_url.startswith("postgresql+psycopg://"):
        pass

    # SSL required on Render Postgres
    if "sslmode=" not in database_url:
        sep = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{sep}sslmode=require"

    return database_url


def init_db(app):
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required")

    database_url = _normalize_database_url(database_url)

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # IMPORTANT: do not pass unknown keys into create_engine via engine_from_config
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
    }

    db.init_app(app)
    migrate.init_app(app, db)

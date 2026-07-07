from __future__ import annotations

import os

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()


def _normalize_database_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is required")

    if url.startswith(("sqlite:///", "sqlite+pysqlite:///")):
        return url

    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)

    if url.startswith("postgresql://") and "+psycopg" not in url:
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)

    return url


def init_db(app):
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    app_env = (os.getenv("APP_ENV") or "production").strip().lower()
    is_production = app_env == "production" or (os.getenv("RENDER") or "").strip().lower() == "true"

    if not database_url:
        if is_production:
            raise RuntimeError("DATABASE_URL is required in production")
        database_url = "sqlite:///freightpay.db"

    database_url = _normalize_database_url(database_url)

    engine_options = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    if database_url.startswith("sqlite"):
        engine_options["connect_args"] = {"check_same_thread": False}
    elif database_url.startswith("postgresql"):
        # Fail fast instead of hanging the boot if the DB is unreachable —
        # a hung connection would trip gunicorn's worker timeout and kill
        # the whole deploy.
        engine_options["connect_args"] = {"connect_timeout": 10}

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options

    db.init_app(app)
    migrate.init_app(app, db)

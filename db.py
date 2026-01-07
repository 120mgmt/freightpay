# db.py
# PRODUCTION-SAFE DB + MIGRATIONS (Render / psycopg3 compatible)

from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()


def _normalize_database_url(url: str) -> str:
    # Render compatibility (postgres:// -> postgresql://)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    # If no explicit driver is specified, force psycopg3 so it never tries psycopg2
    parts = urlsplit(url)
    scheme = parts.scheme

    # Examples:
    #   postgresql://...          -> postgresql+psycopg://...
    #   postgresql+psycopg://...  -> unchanged
    if scheme == "postgresql":
        scheme = "postgresql+psycopg"

    return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))


def init_db(app):
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    database_url = _normalize_database_url(database_url)

    app.config.update(
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            "pool_pre_ping": True,
            "pool_recycle": 300,
        },
    )

    db.init_app(app)
    migrate.init_app(app, db)

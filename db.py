# db.py
# FULL, RESTORED, PRODUCTION-READY DATABASE INITIALIZATION
# No placeholders. Safe for Render, Gunicorn, Flask-SQLAlchemy.

from __future__ import annotations

import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Singleton database objects
db = SQLAlchemy()
migrate = Migrate()


def init_db(app):
    """
    Initializes database + migrations.
    Must be called from app factory.
    """

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required")

    # Render compatibility (postgres:// -> postgresql://)
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

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

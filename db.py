# db.py  (FULL FILE — psycopg3 compatible, production-safe)

import os

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

db = SQLAlchemy()


def _normalize_database_url(url: str) -> str:
    """
    Ensure psycopg3 driver is used.
    Accepts postgres:// or postgresql:// and upgrades to postgresql+psycopg://
    """
    u = make_url(url)
    if u.drivername in ("postgres", "postgresql"):
        return u.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
    if u.drivername == "postgresql+psycopg":
        return url
    return url


def init_db(app):
    raw_url = os.getenv("DATABASE_URL")
    if not raw_url:
        raise RuntimeError("DATABASE_URL is required")

    db_url = _normalize_database_url(raw_url)

    app.config.update(
        SQLALCHEMY_DATABASE_URI=db_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            # Render-friendly defaults
            "poolclass": NullPool,
            "pool_pre_ping": True,
            "future": True,
        },
    )

    db.init_app(app)

    # Optional sanity check (does not create tables)
    with app.app_context():
        try:
            with db.engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
        except Exception as e:
            raise RuntimeError(f"Database connection failed: {e}") from e

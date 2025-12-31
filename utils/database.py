# utils/database.py

from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.orm.session import Session

Base = declarative_base()

# Render sets DATABASE_URL for Postgres. We also support SQLite for local/dev.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///freightpay.db").strip()

# Render Postgres URLs sometimes start with postgres:// (SQLAlchemy expects postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Session:
    """
    Returns a SQLAlchemy Session.
    - If running inside a Flask request context, reuses one session per request via flask.g
    - Otherwise, returns a fresh session (caller must close)
    """
    try:
        from flask import g  # type: ignore

        db: Optional[Session] = getattr(g, "_db_session", None)
        if db is None:
            db = SessionLocal()
            g._db_session = db
        return db
    except Exception:
        # Not in a Flask request context
        return SessionLocal()


def close_db(e: Exception | None = None) -> None:
    """
    Closes the per-request session if present.
    Safe to call multiple times.
    """
    try:
        from flask import g  # type: ignore

        db: Optional[Session] = getattr(g, "_db_session", None)
        if db is not None:
            db.close()
            g._db_session = None
    except Exception:
        return


def init_db(app) -> None:
    """
    Register teardown hook to close DB session after each request.
    Call once from app factory.
    """
    try:
        app.teardown_appcontext(close_db)
    except Exception:
        return


# Backward-compatible helper name (if any older code calls it)
def get_db_session() -> Session:
    return get_db()

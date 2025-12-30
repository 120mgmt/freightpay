import os

from sqlalchemy.orm import declarative base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

Base = declarative_base()
# Render sets DATABASE_URL for Postgres. We also support SQLite for local/dev.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///freightpay.db")

# Render Postgres URLs sometimes start with postgres:// (SQLAlchemy expects postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db_session():
    """Simple helper: returns a SQLAlchemy session (remember to close it)."""
    return SessionLocal()

"""Database connection layer for Neon PostgreSQL.

Connection string is read from the DATABASE_URL environment variable.
No credentials are hardcoded.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL")

Base = declarative_base()

_engine = None

# A connection that cannot be made must fail, not wait. Without it a Neon connection
# is bounded only by the operating system's TCP timeout, and the world-gold database
# fallback -- the path a degraded network reaches -- could hold a run to the 20-minute
# job timeout like the Kitco read did (SP_C_HANDOFF.md sections 33.2, 42, 43). libpq
# applies it to each address in turn; Neon's pooler resolves to three, so a dead
# connection fails within about 30 s. A suspended Neon compute wakes in about a second.
CONNECT_TIMEOUT_SECONDS = 10


def _connect_args(url):
    """libpq's connect_timeout for PostgreSQL. Other drivers (the KPI suite's in-memory
    SQLite) do not accept it."""
    return {"connect_timeout": CONNECT_TIMEOUT_SECONDS} if url.startswith("postgres") else {}


def get_engine():
    """Return the SQLAlchemy engine, or None if DATABASE_URL is not set."""
    global _engine
    if _engine is None and DATABASE_URL:
        _engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args=_connect_args(DATABASE_URL),
        )
    return _engine


def get_session():
    """Return a new database session, or None if DATABASE_URL is not set."""
    engine = get_engine()
    if engine is None:
        return None
    return sessionmaker(bind=engine)()


def init_db():
    """Create all tables. Raises if DATABASE_URL is not configured."""
    engine = get_engine()
    if engine is None:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Cannot initialize database."
        )
    Base.metadata.create_all(bind=engine)

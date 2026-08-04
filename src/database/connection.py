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


def get_engine():
    """Return the SQLAlchemy engine, or None if DATABASE_URL is not set."""
    global _engine
    if _engine is None and DATABASE_URL:
        _engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=300,
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

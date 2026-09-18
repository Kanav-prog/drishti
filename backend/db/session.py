"""Database session and engine configuration."""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

logger = logging.getLogger(__name__)

def _default_db_url() -> str:
    # Keep local development simple while supporting PostgreSQL in production.
    url = os.getenv("DATABASE_URL", "sqlite:///./drishti.db")
    # Log first 50 chars only (don't leak password)
    safe_url = url[:50] + "..." if len(url) > 50 else url
    logger.info(f"📊 Database URL configured: {safe_url}")
    return url


DATABASE_URL = _default_db_url()

_engine_kwargs = {
    "future": True,
    "pool_pre_ping": True,
    "pool_recycle": 3600,  # Recycle connections every hour
}

if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL connection pooling
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10

try:
    engine = create_engine(DATABASE_URL, **_engine_kwargs)
    logger.info("✅ SQLAlchemy engine created successfully")
except Exception as e:
    logger.error(f"❌ Failed to create SQLAlchemy engine: {e}")
    raise

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def test_database_connection(verbose: bool = False) -> bool:
    """Test if database is accessible."""
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))
        if verbose:
            logger.info("✅ Database connection successful")
        return True
    except Exception as e:
        logger.error(f"❌ Database connection FAILED: {e}")
        return False


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

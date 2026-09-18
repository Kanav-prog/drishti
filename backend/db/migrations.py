"""Simple SQL migration runner with schema versioning support."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import re
import time
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from backend.db import models  # noqa: F401 - Ensure ORM models are registered
from backend.db.session import Base
from backend.db.session import engine

logger = logging.getLogger(__name__)


MIGRATION_FILE_PATTERN = re.compile(r"^(\d{3})_.*\.sql$")


def _migration_dir() -> Path:
    return Path(__file__).parent / "migrations"


def ensure_migration_table(retries: int = 3) -> None:
    """Create migration table with retry logic."""
    for attempt in range(retries):
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS schema_migrations (
                            version VARCHAR(64) PRIMARY KEY,
                            applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
            logger.info(f"✅ Migration table ensured on attempt {attempt + 1}")
            return
        except OperationalError as e:
            if attempt < retries - 1:
                wait_time = 2 ** attempt  # exponential backoff
                logger.warning(f"⚠️ Database not yet ready (attempt {attempt + 1}/{retries}). Retrying in {wait_time}s... Error: {e}")
                time.sleep(wait_time)
            else:
                logger.error(f"❌ Failed to ensure migration table after {retries} attempts: {e}")
                raise
        except Exception as e:
            logger.error(f"❌ Unexpected error creating migration table: {e}")
            raise


def applied_versions() -> set[str]:
    ensure_migration_table()
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT version FROM schema_migrations")).fetchall()
    return {str(r[0]) for r in rows}


def _read_migrations() -> list[tuple[str, Path]]:
    migrations: list[tuple[str, Path]] = []
    for path in sorted(_migration_dir().glob("*.sql")):
        match = MIGRATION_FILE_PATTERN.match(path.name)
        if not match:
            continue
        migrations.append((match.group(1), path))
    return migrations


def _split_sql_statements(sql: str) -> Iterable[str]:
    # Simple statement splitter for migration files that contain multiple DDL statements.
    for part in sql.split(";"):
        statement = part.strip()
        if statement:
            yield statement


def run_migrations() -> list[str]:
    """Apply pending migrations and return applied versions."""
    try:
        logger.info("🔄 Starting database migrations...")
        ensure_migration_table()
        applied = applied_versions()
        
        if applied:
            logger.info(f"📦 Already applied migrations: {applied}")
        
        executed: list[str] = []

        for version, path in _read_migrations():
            if version in applied:
                logger.debug(f"⏭️  Skipping already-applied migration: {version}")
                continue
            
            logger.info(f"▶️  Applying migration: {version}")
            try:
                sql = path.read_text(encoding="utf-8")
                with engine.begin() as conn:
                    # Make the initial schema portable for SQLite/PostgreSQL/MySQL.
                    if version == "001":
                        Base.metadata.create_all(bind=conn)
                    for statement in _split_sql_statements(sql):
                        conn.execute(text(statement))
                    conn.execute(
                        text("INSERT INTO schema_migrations(version, applied_at) VALUES (:version, :applied_at)"),
                        {"version": version, "applied_at": datetime.now(timezone.utc)},
                    )
                executed.append(version)
                logger.info(f"✅ Migration {version} applied successfully")
            except Exception as e:
                logger.error(f"❌ Migration {version} FAILED: {e}")
                raise

        if executed:
            logger.info(f"🎉 Successfully applied {len(executed)} migrations: {executed}")
        else:
            logger.info("✅ Database already up to date")
        
        return executed
    except Exception as e:
        logger.error(f"❌ CRITICAL: Database initialization failed: {e}")
        raise

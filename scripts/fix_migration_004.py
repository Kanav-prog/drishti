#!/usr/bin/env python3
"""Emergency script: removes the failed 004 migration record so the corrected SQL can re-run."""
import sys
import os

sys.path.insert(0, '/app')

from sqlalchemy import text
from backend.db.session import engine

with engine.begin() as conn:
    result = conn.execute(text("SELECT version FROM schema_migrations WHERE version = '004'"))
    rows = result.fetchall()
    if rows:
        conn.execute(text("DELETE FROM schema_migrations WHERE version = '004'"))
        print("✅ Removed failed migration record '004' — it will retry on next restart.")
    else:
        print("ℹ️  Migration '004' not found in schema_migrations (already cleaned up or never ran).")
    
    # Also verify current state
    all_migrations = conn.execute(text("SELECT version, applied_at FROM schema_migrations ORDER BY version")).fetchall()
    print(f"\n📋 Applied migrations: {[r[0] for r in all_migrations]}")

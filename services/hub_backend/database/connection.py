"""
Smart Spectator - SQLite Connection & Transaction Manager
"""

import sqlite3
import threading
from contextlib import contextmanager
from typing import Generator
from ..config import settings
from .schema import CREATE_TABLES_SQL


_local = threading.local()


def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict:
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}


def get_db_connection() -> sqlite3.Connection:
    """Returns a thread-local SQLite connection with WAL enabled."""
    current_path = str(settings.DATABASE_PATH)
    if (
        not hasattr(_local, "connection")
        or _local.connection is None
        or getattr(_local, "db_path", None) != current_path
    ):
        if hasattr(_local, "connection") and _local.connection:
            try:
                _local.connection.close()
            except Exception:
                pass
        conn = sqlite3.connect(
            current_path,
            timeout=30.0,
            check_same_thread=False
        )
        conn.row_factory = dict_factory
        # Apply WAL and foreign key pragmas on every connection
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        _local.connection = conn
        _local.db_path = current_path
    return _local.connection


@contextmanager
def db_session() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for atomic SQLite transactions."""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_database() -> None:
    """Executes database schema migration and enforces WAL mode."""
    with db_session() as conn:
        conn.executescript(CREATE_TABLES_SQL)

        # Migrate events table columns if upgrading from Phase 1-3
        cursor = conn.execute("PRAGMA table_info(events);")
        existing_cols = {row["name"] for row in cursor.fetchall()}
        migration_cols = {
            "status": "TEXT NOT NULL DEFAULT 'detected'",
            "start_time": "DATETIME",
            "end_time": "DATETIME",
            "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "zone_id": "TEXT",
            "rule_id": "TEXT",
            "explanation": "TEXT",
        }
        for col, col_def in migration_cols.items():
            if col not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE events ADD COLUMN {col} {col_def};")
                except Exception:
                    pass

        # Verify WAL mode
        cursor = conn.execute("PRAGMA journal_mode;")
        row = cursor.fetchone()
        journal_mode = row.get("journal_mode") if row else "unknown"
        print(f"[Database] Initialized at {settings.DATABASE_PATH}. Mode: {journal_mode.upper()}")

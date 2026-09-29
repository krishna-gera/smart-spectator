"""
Smart Spectator - Database Local Backup and Restore Module
Conforms to Section 18 of Phase 6 Master Specification.
Safely exports/imports database metadata, rules, zones, and events without duplicating video files.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tarfile
import tempfile
from typing import Dict, Any, Optional

from services.hub_backend.config import settings
from services.hub_backend.database.connection import db_session


def export_database_backup(output_dir: Optional[Path] = None) -> Path:
    """
    Exports a consistent SQLite database backup using SQLite's online backup API,
    accompanied by a JSON metadata manifest.
    Does not copy heavy MP4 recordings, preserving disk storage.
    """
    target_dir = output_dir or settings.BACKUP_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_filename = f"smart_spectator_backup_{timestamp_str}.db"
    backup_path = target_dir / backup_filename

    # Perform online SQLite backup
    with db_session() as src_conn:
        dest_conn = sqlite3.connect(str(backup_path))
        try:
            src_conn.backup(dest_conn, pages=100, sleep=0.01)
        finally:
            dest_conn.close()

    # Generate metadata manifest
    manifest = {
        "backup_file": backup_filename,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "app_version": settings.APP_VERSION,
        "schema_version": settings.SCHEMA_VERSION,
        "database_size_bytes": backup_path.stat().st_size,
    }
    manifest_path = target_dir / f"manifest_{timestamp_str}.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return backup_path


def restore_database_backup(backup_path: Path) -> Dict[str, Any]:
    """
    Restores the database from an exported backup file after verifying schema integrity.
    Creates a pre-restore safety snapshot of the active database before applying.
    """
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found at: {backup_path}")

    # Validate that backup is a readable SQLite database
    try:
        test_conn = sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)
        try:
            cursor = test_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            required_tables = {"cameras", "events", "zones", "event_rules"}
            if not required_tables.issubset(tables):
                raise ValueError(f"Backup file is corrupted or not a valid SQLite database. Missing tables: {required_tables - tables}")
        finally:
            test_conn.close()
    except (sqlite3.DatabaseError, sqlite3.OperationalError) as exc:
        raise ValueError(f"Backup file is corrupted or not a valid SQLite database: {exc}") from exc

    # Create safety snapshot of current active DB
    active_db = settings.DATABASE_PATH
    if active_db.exists():
        safety_path = settings.BACKUP_DIR / f"pre_restore_safety_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.db"
        with sqlite3.connect(str(active_db)) as src:
            with sqlite3.connect(str(safety_path)) as dst:
                src.backup(dst)

    # Perform restore using online backup API in reverse
    with sqlite3.connect(str(backup_path)) as src:
        with sqlite3.connect(str(active_db)) as dst:
            src.backup(dst)

    return {
        "status": "restored",
        "schema_version": settings.SCHEMA_VERSION,
        "restored_from": str(backup_path),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "verified_tables": list(tables),
    }

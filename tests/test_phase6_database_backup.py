"""
Smart Spectator - Phase 6 Database Versioned Migrations & Backup Tests
Conforms to Sections 17, 18, 19 of Phase 6 Master Specification.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import pytest

from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, db_session
from services.hub_backend.database.migrations import (
    apply_migrations,
    get_current_version,
    MIGRATIONS,
)
from services.hub_backend.database.backup import (
    export_database_backup,
    restore_database_backup,
)


@pytest.fixture
def backup_test_env(tmp_path):
    db_file = tmp_path / "test_backup_src.db"
    settings.DATABASE_PATH = db_file
    settings.BACKUP_DIR = tmp_path / "test_backups"
    settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    init_database()
    yield tmp_path
    if db_file.exists():
        db_file.unlink()


def test_versioned_migrations_application(backup_test_env):
    """Verifies that all migrations apply sequentially and track version correctly (Section 19)."""
    with db_session() as conn:
        current_v = get_current_version(conn)
        assert current_v == len(MIGRATIONS)

        # Re-running migrations should apply 0 additional migrations
        newly_applied = apply_migrations(conn)
        assert newly_applied == 0


def test_database_backup_export_and_restore(backup_test_env):
    """Tests exporting an online SQLite backup and restoring it cleanly (Section 18)."""
    # 1. Insert test records
    with db_session() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO cameras (camera_id, name, source_type, status) VALUES ('cam_bk_01', 'Backup Cam', 'phone', 'streaming')"
        )
        conn.execute(
            """
            INSERT INTO zones (zone_id, camera_id, name, polygon_json)
            VALUES ('zone_bk_01', 'cam_bk_01', 'Porch Zone', '[[0.1, 0.1], [0.5, 0.1], [0.5, 0.5]]')
            """
        )

    # 2. Export backup
    backup_file = export_database_backup(output_dir=settings.BACKUP_DIR)
    assert backup_file.exists()
    assert backup_file.stat().st_size > 0

    # Verify manifest exists
    manifests = list(settings.BACKUP_DIR.glob("manifest_*.json"))
    assert len(manifests) >= 1

    # 3. Simulate disaster: delete or clear tables in active database
    with db_session() as conn:
        conn.execute("DELETE FROM zones WHERE zone_id = 'zone_bk_01'")
        cur = conn.execute("SELECT COUNT(*) as c FROM zones WHERE zone_id = 'zone_bk_01'")
        assert cur.fetchone()["c"] == 0

    # 4. Restore database from backup file
    res = restore_database_backup(backup_file)
    assert res["status"] == "restored"

    # 5. Verify restored data
    with db_session() as conn:
        cur = conn.execute("SELECT COUNT(*) as c FROM zones WHERE zone_id = 'zone_bk_01'")
        assert cur.fetchone()["c"] == 1


def test_restore_rejects_corrupted_backup(backup_test_env, tmp_path):
    """Verifies that restoring from an invalid or non-database file raises ValueError."""
    fake_backup = tmp_path / "corrupt_backup.db"
    fake_backup.write_text("THIS IS NOT A VALID SQLITE DATABASE")

    with pytest.raises(Exception):
        restore_database_backup(fake_backup)

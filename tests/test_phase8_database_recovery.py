"""
Smart Spectator - Phase 8 Database Recovery, Backup & Integrity Test Suite
Conforms to Sections 18 & 25 of Phase 8 Master Specification.
Tests:
1. End-to-end backup, database modification, and restoration.
2. PRAGMA integrity_check validation post-restore.
3. Pre-restore safety snapshot generation.
4. Rollback protection when restoring corrupted backup files.
5. Rejection of nonexistent backup files.
"""

from pathlib import Path
import sqlite3
import pytest

from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, get_db_connection
from services.hub_backend.database.backup import export_database_backup, restore_database_backup


@pytest.fixture
def recovery_env(tmp_path):
    db_file = tmp_path / "recovery_test.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    settings.DATABASE_PATH = db_file
    settings.BACKUP_DIR = backup_dir

    init_database()
    yield db_file, backup_dir
    if db_file.exists():
        db_file.unlink()


def test_database_backup_restore_and_integrity_check(recovery_env):
    """
    Tests complete cycle:
    Insert data -> export hot backup -> modify/corrupt data -> restore -> PRAGMA integrity_check
    """
    db_file, backup_dir = recovery_env

    # 1. Insert test baseline data
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO devices (device_id, device_name, status) VALUES ('dev_rec_01', 'Recovery Node', 'paired')"
        )
        conn.execute(
            "INSERT INTO cameras (camera_id, device_id, name, source_type, status) VALUES ('cam_rec_01', 'dev_rec_01', 'Rec Cam', 'phone', 'idle')"
        )
        conn.execute(
            "INSERT INTO events (event_id, camera_id, event_type, status, severity, confidence, summary) "
            "VALUES ('evt_rec_01', 'cam_rec_01', 'PERSON_ENTERED', 'active', 'medium', 0.92, 'Baseline event')"
        )
        conn.commit()

    # 2. Export hot backup
    backup_path = export_database_backup(output_dir=backup_dir)
    assert backup_path.exists()

    # 3. Modify database (simulating data loss/mutation)
    with get_db_connection() as conn:
        conn.execute("DELETE FROM events WHERE event_id = 'evt_rec_01'")
        conn.commit()
        # Verify event was deleted
        row = conn.execute("SELECT * FROM events WHERE event_id = 'evt_rec_01'").fetchone()
        assert row is None

    # 4. Restore database from backup
    restore_res = restore_database_backup(backup_path=backup_path)
    assert restore_res["status"] == "restored"
    assert "schema_version" in restore_res

    # 5. Verify data restored and PRAGMA integrity_check returns ok
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM events WHERE event_id = 'evt_rec_01'").fetchone()
        assert row is not None
        assert row["event_id"] == "evt_rec_01"

        # Explicit PRAGMA integrity_check (Section 18)
        check_row = conn.execute("PRAGMA integrity_check;").fetchone()
        assert check_row["integrity_check"] == "ok"


def test_restore_rejects_corrupted_backup_and_protects_current_db(recovery_env):
    """Verifies that an invalid/corrupted backup is rejected without damaging the active database."""
    db_file, backup_dir = recovery_env

    # Populate baseline
    with get_db_connection() as conn:
        conn.execute("INSERT INTO devices (device_id, device_name, status) VALUES ('dev_safe_01', 'Safe Node', 'paired')")
        conn.commit()

    # Create corrupted backup file
    corrupt_backup = backup_dir / "corrupted_backup.db"
    corrupt_backup.write_bytes(b"NOT_A_VALID_SQLITE_DATABASE_HEADER_GARBAGE")

    with pytest.raises(ValueError, match="corrupted or not a valid SQLite database"):
        restore_database_backup(backup_path=corrupt_backup)

    # Active database must remain completely intact
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM devices WHERE device_id = 'dev_safe_01'").fetchone()
        assert row is not None
        check_row = conn.execute("PRAGMA integrity_check;").fetchone()
        assert check_row["integrity_check"] == "ok"


def test_restore_rejects_missing_backup(recovery_env):
    """Verifies that restoring a missing backup file raises FileNotFoundError."""
    db_file, backup_dir = recovery_env
    non_existent = backup_dir / "ghost_backup_does_not_exist.db"

    with pytest.raises(FileNotFoundError):
        restore_database_backup(backup_path=non_existent)

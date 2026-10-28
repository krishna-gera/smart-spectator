"""
Smart Spectator - Device Repository
Encapsulates all database operations for camera devices.
"""

from typing import List, Dict, Any, Optional
from services.hub_backend.database.connection import db_session


class DeviceRepository:
    def list_devices(self) -> List[Dict[str, Any]]:
        with db_session() as conn:
            cursor = conn.execute("SELECT * FROM devices ORDER BY paired_at DESC")
            return cursor.fetchall()

    def get_by_id(self, device_id: str) -> Optional[Dict[str, Any]]:
        with db_session() as conn:
            cursor = conn.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,))
            return cursor.fetchone()

    def count_active(self) -> int:
        with db_session() as conn:
            row = conn.execute("SELECT COUNT(*) as c FROM devices WHERE status IN ('paired', 'connected')").fetchone()
            return row["c"] if row else 0

    def count_unrevoked(self) -> int:
        with db_session() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM devices WHERE revoked = 0").fetchone()
            return row["cnt"] if row else 0


device_repository = DeviceRepository()

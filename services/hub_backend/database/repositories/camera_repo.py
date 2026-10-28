"""
Smart Spectator - Camera Repository
Encapsulates all database operations for camera nodes.
"""

from typing import List, Dict, Any, Optional
from services.hub_backend.database.connection import db_session


class CameraRepository:
    def list_all(self) -> List[Dict[str, Any]]:
        with db_session() as conn:
            cur = conn.execute("SELECT * FROM cameras ORDER BY created_at ASC")
            return cur.fetchall()

    def get_by_id(self, camera_id: str) -> Optional[Dict[str, Any]]:
        with db_session() as conn:
            cur = conn.execute("SELECT * FROM cameras WHERE camera_id = ?", (camera_id,))
            return cur.fetchone()

    def update_name(self, camera_id: str, name: str) -> Optional[Dict[str, Any]]:
        with db_session() as conn:
            conn.execute("UPDATE cameras SET name = ? WHERE camera_id = ?", (name, camera_id))
            cur = conn.execute("SELECT * FROM cameras WHERE camera_id = ?", (camera_id,))
            return cur.fetchone()

    def update_status(self, camera_id: str, status: str) -> bool:
        with db_session() as conn:
            cur = conn.execute("UPDATE cameras SET status = ? WHERE camera_id = ?", (status, camera_id))
            return cur.rowcount > 0

    def upsert(self, camera_id: str, name: str, source_type: str = "phone", status: str = "idle") -> None:
        with db_session() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO cameras (camera_id, name, source_type, status)
                VALUES (?, ?, ?, ?)
                """,
                (camera_id, name, source_type, status),
            )

    def count_active(self) -> int:
        with db_session() as conn:
            row = conn.execute("SELECT COUNT(*) as c FROM cameras WHERE status = 'streaming'").fetchone()
            return row["c"] if row else 0

    def count_total(self) -> int:
        with db_session() as conn:
            row = conn.execute("SELECT COUNT(*) as c FROM cameras").fetchone()
            return row["c"] if row else 0


camera_repository = CameraRepository()

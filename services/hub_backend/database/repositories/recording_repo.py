"""
Smart Spectator - Recording Repository
Encapsulates all database operations for video recording clips.
"""

from typing import List, Dict, Any, Optional
from services.hub_backend.database.connection import db_session


class RecordingRepository:
    def list_recordings(
        self,
        camera_id: Optional[str] = None,
        is_locked: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM recordings WHERE 1=1"
        params: List[Any] = []

        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        if is_locked is not None:
            query += " AND is_locked = ?"
            params.append(1 if is_locked else 0)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with db_session() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()

    def get_by_id(self, recording_id: str) -> Optional[Dict[str, Any]]:
        with db_session() as conn:
            cursor = conn.execute("SELECT * FROM recordings WHERE recording_id = ?", (recording_id,))
            return cursor.fetchone()

    def toggle_lock(self, recording_id: str) -> Optional[bool]:
        with db_session() as conn:
            cursor = conn.execute("SELECT is_locked FROM recordings WHERE recording_id = ?", (recording_id,))
            row = cursor.fetchone()
            if not row:
                return None
            new_lock = 0 if row["is_locked"] else 1
            conn.execute("UPDATE recordings SET is_locked = ? WHERE recording_id = ?", (new_lock, recording_id))
            return bool(new_lock)

    def get_thumbnail_path(self, recording_id: str) -> Optional[str]:
        with db_session() as conn:
            cursor = conn.execute("SELECT thumbnail_path FROM recordings WHERE recording_id = ?", (recording_id,))
            row = cursor.fetchone()
            return row["thumbnail_path"] if row else None

    def delete_record(self, recording_id: str) -> bool:
        with db_session() as conn:
            conn.execute("DELETE FROM recordings WHERE recording_id = ?", (recording_id,))
            conn.execute("UPDATE events SET recording_id = NULL WHERE recording_id = ?", (recording_id,))
            return True


recording_repository = RecordingRepository()

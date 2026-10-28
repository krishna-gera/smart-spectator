"""
Smart Spectator - Zone Repository
Encapsulates all database operations for detection zones.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from services.hub_backend.database.connection import db_session


class ZoneRepository:
    def list_zones(self, camera_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with db_session() as conn:
            if camera_id:
                cursor = conn.execute("SELECT * FROM zones WHERE camera_id = ? ORDER BY created_at ASC", (camera_id,))
            else:
                cursor = conn.execute("SELECT * FROM zones ORDER BY created_at ASC")
            return cursor.fetchall()

    def get_by_id(self, zone_id: str) -> Optional[Dict[str, Any]]:
        with db_session() as conn:
            cursor = conn.execute("SELECT * FROM zones WHERE zone_id = ?", (zone_id,))
            return cursor.fetchone()

    def create(
        self,
        zone_id: str,
        camera_id: str,
        name: str,
        polygon_json: str,
        color: str = "#38bdf8",
        is_active: bool = True,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> None:
        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO zones (zone_id, camera_id, name, polygon_json, color, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), COALESCE(?, CURRENT_TIMESTAMP))
                """,
                (zone_id, camera_id, name, polygon_json, color, 1 if is_active else 0, created_at, updated_at),
            )

    def update(
        self,
        zone_id: str,
        name: Optional[str] = None,
        polygon_json: Optional[str] = None,
        color: Optional[str] = None,
        is_active: Optional[bool] = None,
        updated_at: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with db_session() as conn:
            cursor = conn.execute("SELECT * FROM zones WHERE zone_id = ?", (zone_id,))
            row = cursor.fetchone()
            if not row:
                return None

            new_name = name if name is not None else row["name"]
            new_poly = polygon_json if polygon_json is not None else row["polygon_json"]
            new_color = color if color is not None else row.get("color", "#38bdf8")
            new_active = (1 if is_active else 0) if is_active is not None else row["is_active"]
            new_updated = updated_at if updated_at is not None else datetime.now(timezone.utc).isoformat()

            conn.execute(
                """
                UPDATE zones
                SET name = ?, polygon_json = ?, color = ?, is_active = ?, updated_at = ?
                WHERE zone_id = ?
                """,
                (new_name, new_poly, new_color, new_active, new_updated, zone_id),
            )
            cursor = conn.execute("SELECT * FROM zones WHERE zone_id = ?", (zone_id,))
            return cursor.fetchone()

    def delete(self, zone_id: str) -> Optional[Dict[str, Any]]:
        with db_session() as conn:
            cursor = conn.execute("SELECT camera_id, name FROM zones WHERE zone_id = ?", (zone_id,))
            row = cursor.fetchone()
            if not row:
                return None
            conn.execute("DELETE FROM zones WHERE zone_id = ?", (zone_id,))
            return row


zone_repository = ZoneRepository()

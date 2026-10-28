"""
Smart Spectator - Event Repository
Encapsulates all database operations for security events and observations.
"""

from typing import List, Dict, Any, Optional
from services.hub_backend.database.connection import db_session


class EventRepository:
    def get_stats(self) -> Dict[str, Any]:
        with db_session() as conn:
            total = conn.execute("SELECT COUNT(*) as c FROM events").fetchone()["c"]
            active = conn.execute(
                "SELECT COUNT(*) as c FROM events WHERE status IN ('detected', 'confirmed', 'active')"
            ).fetchone()["c"]
            p_rows = conn.execute("SELECT priority, COUNT(*) as c FROM events GROUP BY priority").fetchall()
            t_rows = conn.execute(
                "SELECT event_type, COUNT(*) as c FROM events GROUP BY event_type ORDER BY c DESC LIMIT 10"
            ).fetchall()
            s_rows = conn.execute("SELECT severity, COUNT(*) as c FROM events GROUP BY severity").fetchall()
            recent = conn.execute(
                "SELECT COUNT(*) as c FROM events WHERE timestamp >= datetime('now', '-24 hours')"
            ).fetchone()["c"]

            by_priority = {r["priority"]: r["c"] for r in p_rows}
            return {
                "total_events": total,
                "active_events": active,
                "events_last_24h": recent,
                "by_priority": {
                    "CRITICAL": by_priority.get("CRITICAL", 0),
                    "HIGH": by_priority.get("HIGH", 0),
                    "MEDIUM": by_priority.get("MEDIUM", 0),
                    "LOW": by_priority.get("LOW", 0),
                },
                "by_type": {r["event_type"]: r["c"] for r in t_rows},
                "by_severity": {r["severity"]: r["c"] for r in s_rows},
            }

    def list_events(
        self,
        camera_id: Optional[str] = None,
        event_type: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        severity: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM events WHERE 1=1"
        params: List[Any] = []

        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if status:
            query += " AND status = ?"
            params.append(status)
        if priority:
            query += " AND priority = ?"
            params.append(priority)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with db_session() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()

    def get_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        with db_session() as conn:
            cursor = conn.execute("SELECT * FROM events WHERE event_id = ?", (event_id,))
            return cursor.fetchone()

    def get_event_time_range(self, event_id: str) -> Optional[Dict[str, Any]]:
        with db_session() as conn:
            cursor = conn.execute(
                "SELECT camera_id, timestamp, start_time, end_time FROM events WHERE event_id = ?",
                (event_id,),
            )
            return cursor.fetchone()

    def get_prediction_history_for_window(
        self, camera_id: str, start_time: str, end_time: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        with db_session() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM event_predictions
                WHERE camera_id = ? AND timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp ASC LIMIT ?
                """,
                (camera_id, start_time, end_time, limit),
            )
            return cursor.fetchall()

    def count_recent_by_camera(self, camera_id: str, since_iso: str) -> int:
        with db_session() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) as c FROM events WHERE camera_id = ? AND timestamp >= ?",
                (camera_id, since_iso),
            )
            row = cursor.fetchone()
            return row["c"] if row else 0


event_repository = EventRepository()

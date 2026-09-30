"""
Smart Spectator - Local Event Memory & History Analysis
Conforms to Sections 6 & 7 of Phase 10 Specification.
Provides privacy-preserving local memory queries without cloud/vector dependencies.
"""

from datetime import datetime, timezone, timedelta
import json
import logging
from typing import Dict, Any, List, Optional, Tuple

from services.hub_backend.database.connection import get_db

logger = logging.getLogger("LocalEventMemory")


class LocalEventMemory:
    """
    Manages long-term local event memories, aggregations, and deterministic historical queries.
    Strictly local SQLite operations.
    """

    def get_events_count(
        self,
        event_type: Optional[str] = None,
        camera_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> int:
        """Counts events matching specified parameters within a time window."""
        query = "SELECT COUNT(*) FROM events WHERE 1=1"
        params: List[Any] = []

        if event_type:
            query += " AND LOWER(event_type) = LOWER(?)"
            params.append(event_type)
        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)

        with get_db() as conn:
            cursor = conn.execute(query, tuple(params))
            row = cursor.fetchone()
            if not row:
                return 0
            return row[0] if isinstance(row, tuple) else list(row.values())[0]

    def get_top_cameras_by_activity(
        self,
        since_time: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Returns cameras ranked by total event count."""
        query = "SELECT camera_id, COUNT(*) as event_count FROM events WHERE 1=1"
        params: List[Any] = []
        if since_time:
            query += " AND timestamp >= ?"
            params.append(since_time)
        query += " GROUP BY camera_id ORDER BY event_count DESC LIMIT ?"
        params.append(limit)

        with get_db() as conn:
            cursor = conn.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [
                {"camera_id": r[0] if not isinstance(r, dict) else r["camera_id"],
                 "event_count": r[1] if not isinstance(r, dict) else r["event_count"]}
                for r in rows
            ]

    def get_events_in_hour_window(
        self,
        start_hour: int = 22,
        end_hour: int = 6,
        date_str: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves events occurring within specific hours of the day (e.g., after 10 PM until 6 AM).
        """
        # Using SQLite strftime('%H', timestamp)
        with get_db() as conn:
            if start_hour > end_hour:  # Crosses midnight (e.g. 22 to 06)
                query = """
                SELECT * FROM events
                WHERE (CAST(strftime('%H', timestamp) AS INTEGER) >= ?
                    OR CAST(strftime('%H', timestamp) AS INTEGER) < ?)
                """
                params = [start_hour, end_hour]
            else:
                query = """
                SELECT * FROM events
                WHERE CAST(strftime('%H', timestamp) AS INTEGER) >= ?
                  AND CAST(strftime('%H', timestamp) AS INTEGER) <= ?
                """
                params = [start_hour, end_hour]

            if date_str:
                query += " AND DATE(timestamp) = DATE(?)"
                params.append(date_str)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, tuple(params))
            rows = cursor.fetchall()
            cols = [col[0] for col in cursor.description]
            return [dict(zip(cols, row)) if not isinstance(row, dict) else row for row in rows]

    def get_daily_activity_summary(self, days: int = 7) -> List[Dict[str, Any]]:
        """Aggregates event counts per day for the last N days."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query = """
        SELECT DATE(timestamp) as event_date, COUNT(*) as count, priority
        FROM events
        WHERE timestamp >= ?
        GROUP BY DATE(timestamp), priority
        ORDER BY event_date ASC
        """
        with get_db() as conn:
            cursor = conn.execute(query, (cutoff,))
            rows = cursor.fetchall()
            summaries: Dict[str, Dict[str, Any]] = {}
            for r in rows:
                d_str = r[0] if not isinstance(r, dict) else r["event_date"]
                cnt = r[1] if not isinstance(r, dict) else r["count"]
                prio = r[2] if not isinstance(r, dict) else r["priority"]
                if d_str not in summaries:
                    summaries[d_str] = {"date": d_str, "total": 0, "by_priority": {}}
                summaries[d_str]["total"] += cnt
                summaries[d_str]["by_priority"][prio] = cnt
            return list(summaries.values())

    def get_recent_relationships(self, limit: int = 50) -> List[Dict[str, Any]]:
        query = "SELECT * FROM event_relationships ORDER BY created_at DESC LIMIT ?"
        with get_db() as conn:
            cursor = conn.execute(query, (limit,))
            rows = cursor.fetchall()
            cols = [col[0] for col in cursor.description]
            results = []
            for row in rows:
                d = dict(zip(cols, row)) if not isinstance(row, dict) else row
                if "details_json" in d and isinstance(d["details_json"], str):
                    try:
                        d["details"] = json.loads(d["details_json"])
                    except Exception:
                        d["details"] = {}
                results.append(d)
            return results


local_memory = LocalEventMemory()

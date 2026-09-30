"""
Smart Spectator - Context Engine
Conforms to Section 5 of Phase 10 Specification.
Builds contextual state around events without external API calls.
"""

from datetime import datetime, timezone, timedelta
import logging
from typing import Dict, Any, List, Optional

from services.event_engine.context_engine.models import EnvironmentalContext
from services.hub_backend.database.connection import get_db

logger = logging.getLogger("ContextEngine")


class ContextEngine:
    """
    Extracts deterministic temporal, spatial, operational, and system context
    for any event or point in time. 100% local operation.
    """

    def __init__(self, after_hours_start: int = 19, after_hours_end: int = 7):
        self.after_hours_start = after_hours_start
        self.after_hours_end = after_hours_end

    def build_context(
        self,
        camera_id: str,
        event_time: Optional[datetime] = None,
        zone_id: Optional[str] = None,
        zone_name: Optional[str] = None,
        zone_type: Optional[str] = None,
        device_state: Optional[Dict[str, Any]] = None,
        system_state: Optional[Dict[str, Any]] = None,
    ) -> EnvironmentalContext:
        dt = event_time or datetime.now(timezone.utc)
        hour = dt.hour
        weekday = dt.weekday()  # Monday is 0, Sunday is 6
        is_weekend = (weekday in (5, 6))

        # After hours: e.g. >= 19:00 or < 07:00, or weekend
        is_after_hours = is_weekend or (hour >= self.after_hours_start or hour < self.after_hours_end)

        recent_5m = 0
        try:
            with get_db() as conn:
                five_min_ago = (dt - timedelta(minutes=5)).isoformat()
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM events WHERE camera_id = ? AND timestamp >= ?",
                    (camera_id, five_min_ago),
                )
                row = cursor.fetchone()
                if row:
                    recent_5m = row[0] if isinstance(row, tuple) else list(row.values())[0]
                else:
                    recent_5m = 0
        except Exception as e:
            logger.debug(f"Could not query recent events: {e}")

        return EnvironmentalContext(
            timestamp=dt.isoformat(),
            hour_of_day=hour,
            day_of_week=weekday,
            is_weekend=is_weekend,
            is_after_hours=is_after_hours,
            camera_id=camera_id,
            zone_id=zone_id,
            zone_name=zone_name,
            zone_type=zone_type,
            recent_events_count_5m=recent_5m,
            active_events_count=1 if recent_5m > 0 else 0,
            device_state=device_state or {},
            system_state=system_state or {},
        )


context_engine = ContextEngine()

"""
Smart Spectator - Local Notification Dispatcher & Multi-Tier Cooldown Manager
Conforms to Sections 10 & 11 of Phase 9 Master Specification.
Routes verified events to local WebSocket notification subscribers with strict
per-event, per-camera, and global anti-spam cooldown tiers. Zero cloud dependencies.
"""

from datetime import datetime, timezone
import json
import threading
import time
from typing import Dict, Any, Optional, List, Callable
import uuid

from shared.schemas.v1.models import Event, EventPriority, NotificationCategory
from services.hub_backend.database.connection import db_session


DEFAULT_COOLDOWNS = {
    "PERSON_ENTERED": 30.0,
    "OBJECT_REMOVED": 10.0,
    "ZONE_LOITERING": 20.0,
    "CAMERA_BLOCKED": 15.0,
    "OBJECT_MOVED": 15.0,
    "CAMERA_DISCONNECTED": 20.0,
    "CAMERA_STREAM_ERROR": 20.0,
}

EVENT_CATEGORY_MAP = {
    "CAMERA_BLOCKED": NotificationCategory.CRITICAL,
    "OBJECT_REMOVED": NotificationCategory.IMPORTANT,
    "ZONE_LOITERING": NotificationCategory.IMPORTANT,
    "PERSON_ENTERED": NotificationCategory.IMPORTANT,
    "OBJECT_MOVED": NotificationCategory.INFORMATIONAL,
    "OBJECT_PRESENT": NotificationCategory.INFORMATIONAL,
    "PERSON_LEFT": NotificationCategory.INFORMATIONAL,
    "NORMAL_ACTIVITY": NotificationCategory.INFORMATIONAL,
}


class NotificationDispatcher:
    """
    Local Notification Hub with multi-tiered rate limiting:
    1. Global cooldown: Enforces minimum time between any two emitted notifications.
    2. Camera cooldown: Prevents a single chatty camera from saturating the user.
    3. Event-type cooldown: Configurable delay per event type (e.g., PERSON_ENTERED: 30s).
    """

    def __init__(
        self,
        global_cooldown_seconds: float = 2.0,
        camera_cooldown_seconds: float = 5.0,
    ):
        self.global_cooldown_seconds = global_cooldown_seconds
        self.camera_cooldown_seconds = camera_cooldown_seconds
        self._lock = threading.Lock()

        # In-memory rate limiting timestamps: float (seconds since epoch)
        self._last_global_notification: float = 0.0
        self._last_camera_notification: Dict[str, float] = {}
        self._last_event_notification: Dict[str, float] = {}  # key: f"{camera_id}:{event_type}"

        # WebSocket broadcaster callback: fn(event_type: str, payload: Dict[str, Any])
        self._broadcaster: Optional[Callable[[str, Dict[str, Any]], None]] = None

    def set_broadcaster(self, broadcaster: Callable[[str, Dict[str, Any]], None]):
        self._broadcaster = broadcaster

    def get_event_cooldown(self, event_type: str) -> float:
        """Retrieves configured cooldown from database or defaults."""
        try:
            with db_session() as conn:
                row = conn.execute(
                    "SELECT cooldown_seconds FROM notification_configs WHERE event_type = ? AND is_enabled = 1",
                    (event_type,)
                ).fetchone()
                if row:
                    return float(row["cooldown_seconds"])
        except Exception:
            pass
        return DEFAULT_COOLDOWNS.get(event_type, 15.0)

    def is_event_enabled(self, event_type: str) -> bool:
        """Checks if event type is enabled for notification dispatch."""
        try:
            with db_session() as conn:
                row = conn.execute(
                    "SELECT is_enabled FROM notification_configs WHERE event_type = ?",
                    (event_type,)
                ).fetchone()
                if row:
                    return bool(row["is_enabled"])
        except Exception:
            pass
        return True

    def can_dispatch(self, camera_id: str, event_type: str, now: Optional[float] = None) -> bool:
        """Evaluates whether notification passes all 3 cooldown tiers."""
        t = now or time.time()
        with self._lock:
            # 1. Global Cooldown
            if (t - self._last_global_notification) < self.global_cooldown_seconds:
                return False

            # 2. Camera Cooldown
            last_cam = self._last_camera_notification.get(camera_id, 0.0)
            if (t - last_cam) < self.camera_cooldown_seconds:
                return False

            # 3. Event-Type Cooldown
            cooldown_duration = self.get_event_cooldown(event_type)
            key = f"{camera_id}:{event_type}"
            last_evt = self._last_event_notification.get(key, 0.0)
            if (t - last_evt) < cooldown_duration:
                return False

            return True

    def dispatch(self, event: Event) -> Optional[Dict[str, Any]]:
        """
        Dispatches structured notification if within cooldown limits.
        Emits 'NOTIFICATION' WebSocket event and logs delivery.
        """
        if not self.is_event_enabled(event.event_type):
            return None

        now = time.time()
        if not self.can_dispatch(event.camera_id, event.event_type, now):
            return None

        with self._lock:
            self._last_global_notification = now
            self._last_camera_notification[event.camera_id] = now
            self._last_event_notification[f"{event.camera_id}:{event.event_type}"] = now

        category = EVENT_CATEGORY_MAP.get(event.event_type, NotificationCategory.IMPORTANT)
        if event.priority == EventPriority.CRITICAL:
            category = NotificationCategory.CRITICAL

        notification_payload = {
            "notification_id": f"notif_{uuid.uuid4().hex[:10]}",
            "schema_version": "1.2.0",
            "event_id": event.event_id,
            "camera_id": event.camera_id,
            "event_type": event.event_type,
            "priority": event.priority.value if hasattr(event.priority, "value") else str(event.priority),
            "category": category.value if hasattr(category, "value") else str(category),
            "title": f"[{category.value.upper()}] {event.event_type.replace('_', ' ')}",
            "message": event.summary,
            "confidence": round(event.confidence, 2),
            "timestamp": event.timestamp.isoformat(),
            "recording_id": event.recording_id,
            "explanation": event.explanation,
        }

        # Log delivery to database
        try:
            with db_session() as conn:
                conn.execute(
                    """
                    INSERT INTO alert_delivery_log (delivery_id, event_id, channel, status, details, delivered_at)
                    VALUES (?, ?, 'websocket', 'delivered', ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        notification_payload["notification_id"],
                        event.event_id,
                        json.dumps({"category": notification_payload["category"], "priority": notification_payload["priority"]})
                    )
                )
        except Exception as e:
            print(f"[NotificationDispatcher] Failed to log alert delivery: {e}")

        # Broadcast via WebSocket if listener is set
        if self._broadcaster:
            try:
                self._broadcaster("NOTIFICATION", notification_payload)
            except Exception as e:
                print(f"[NotificationDispatcher] Broadcast error: {e}")

        return notification_payload


notification_dispatcher = NotificationDispatcher()

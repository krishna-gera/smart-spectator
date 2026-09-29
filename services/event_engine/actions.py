"""
Smart Spectator - Event Engine: Pluggable Action System
Dispatches actions upon validated event confirmations.
Conforms to Sections 23, 84, 90 of Phase 4 specification.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import uuid
from typing import Dict, Any, List, Optional, Callable

from shared.schemas.v1.models import Event, EventStatus
from services.hub_backend.database.connection import db_session


class ActionContext:
    """Carries context required for action execution."""

    def __init__(
        self,
        event: Event,
        rule_id: Optional[str] = None,
        recorder_fn: Optional[Callable[[Event], Any]] = None,
        websocket_broadcast_fn: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.event = event
        self.rule_id = rule_id
        self.recorder_fn = recorder_fn
        self.websocket_broadcast_fn = websocket_broadcast_fn
        self.metadata = metadata or {}


class Action(ABC):
    """Abstract base class for all pluggable automation actions."""

    @property
    @abstractmethod
    def action_name(self) -> str:
        pass

    @abstractmethod
    def execute(self, context: ActionContext) -> bool:
        pass


class CreateEventAction(Action):
    """Persists or confirms the event in the local database."""

    @property
    def action_name(self) -> str:
        return "CREATE_EVENT"

    def execute(self, context: ActionContext) -> bool:
        event = context.event
        with db_session() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO cameras (camera_id, name, source_type, status)
                VALUES (?, ?, 'phone', 'streaming')
                """,
                (event.camera_id, f"Camera {event.camera_id}"),
            )
            conn.execute(
                """
                INSERT INTO events (
                    event_id, camera_id, task_id, recording_id, event_type,
                    status, severity, confidence, summary, timestamp,
                    start_time, end_time, created_at, updated_at,
                    involved_track_ids, zone_id, rule_id, explanation, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    status = excluded.status,
                    confidence = MAX(events.confidence, excluded.confidence),
                    end_time = excluded.end_time,
                    updated_at = excluded.updated_at,
                    involved_track_ids = excluded.involved_track_ids,
                    recording_id = COALESCE(excluded.recording_id, events.recording_id),
                    explanation = excluded.explanation,
                    metadata_json = excluded.metadata_json
                """,
                (
                    event.event_id,
                    event.camera_id,
                    event.task_id,
                    event.recording_id,
                    event.event_type,
                    event.status.value,
                    event.severity.value,
                    event.confidence,
                    event.summary,
                    event.timestamp.isoformat(),
                    event.start_time.isoformat() if event.start_time else None,
                    event.end_time.isoformat() if event.end_time else None,
                    event.created_at.isoformat(),
                    event.updated_at.isoformat(),
                    json.dumps(event.involved_track_ids),
                    event.zone_id,
                    event.rule_id,
                    event.explanation,
                    json.dumps(event.metadata),
                )
            )
        return True


class SaveClipAction(Action):
    """Triggers rolling media buffer recording and clip preservation."""

    @property
    def action_name(self) -> str:
        return "SAVE_CLIP"

    def execute(self, context: ActionContext) -> bool:
        if context.recorder_fn:
            try:
                context.recorder_fn(context.event)
                return True
            except Exception as e:
                print(f"[SaveClipAction] Error triggering recording: {e}")
                return False
        return False


class ClientNotificationAction(Action):
    """Broadcasts event notification to connected WebSocket clients and logs delivery."""

    @property
    def action_name(self) -> str:
        return "CLIENT_NOTIFICATION"

    def execute(self, context: ActionContext) -> bool:
        event = context.event
        if context.websocket_broadcast_fn:
            try:
                payload = {
                    "event_id": event.event_id,
                    "camera_id": event.camera_id,
                    "event_type": event.event_type,
                    "severity": event.severity.value,
                    "status": event.status.value,
                    "confidence": event.confidence,
                    "summary": event.summary,
                    "explanation": event.explanation,
                    "timestamp": event.timestamp.isoformat(),
                    "zone_id": event.zone_id,
                    "rule_id": event.rule_id,
                }
                context.websocket_broadcast_fn("event_confirmed", payload)
            except Exception as e:
                print(f"[ClientNotificationAction] WebSocket broadcast error: {e}")

        # Log alert delivery
        try:
            with db_session() as conn:
                conn.execute(
                    "INSERT INTO alert_delivery_log (log_id, event_id, channel, status, details) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        str(uuid.uuid4()),
                        event.event_id,
                        "websocket",
                        "delivered",
                        f"Notified clients of {event.event_type}",
                    )
                )
        except Exception:
            pass

        return True


class LogEventAction(Action):
    """Records audit trail entry for confirmed event."""

    @property
    def action_name(self) -> str:
        return "LOG_EVENT"

    def execute(self, context: ActionContext) -> bool:
        event = context.event
        try:
            with db_session() as conn:
                conn.execute(
                    "INSERT INTO audit_logs (log_id, actor, action, resource, metadata_json) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        str(uuid.uuid4()),
                        "event_engine",
                        "event_confirmed",
                        event.event_id,
                        json.dumps({
                            "event_type": event.event_type,
                            "camera_id": event.camera_id,
                            "severity": event.severity.value,
                            "rule_id": context.rule_id,
                        }),
                    )
                )
            return True
        except Exception as e:
            print(f"[LogEventAction] Audit log error: {e}")
            return False


class ActionDispatcher:
    """Manages and executes registered actions."""

    def __init__(self):
        self._actions: Dict[str, Action] = {}
        # Register core initial actions
        self.register_action(CreateEventAction())
        self.register_action(SaveClipAction())
        self.register_action(ClientNotificationAction())
        self.register_action(LogEventAction())

    def register_action(self, action: Action) -> None:
        self._actions[action.action_name] = action

    def dispatch(self, action_name: str, context: ActionContext) -> bool:
        act = self._actions.get(action_name)
        if not act:
            print(f"[ActionDispatcher] Warning: Unknown action '{action_name}' requested.")
            return False

        action_id = str(uuid.uuid4())
        status = "failed"
        error_msg = None

        try:
            success = act.execute(context)
            status = "success" if success else "failed"
            return success
        except Exception as e:
            error_msg = str(e)
            print(f"[ActionDispatcher] Exception executing action '{action_name}': {e}")
            return False
        finally:
            try:
                with db_session() as conn:
                    conn.execute(
                        "INSERT INTO event_actions (action_id, event_id, action_type, status, error) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (action_id, context.event.event_id, action_name, status, error_msg),
                    )
            except Exception:
                pass

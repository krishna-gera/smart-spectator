"""
Smart Spectator - Event Engine Core Orchestrator
Consumes EventPredictions and Observations asynchronously, evaluates policies,
orchestrates lifecycle state transitions, dispatches actions, and triggers recordings.
Conforms to Sections 4, 5, 6, 7, 8, 9, 10, 11, 16, 28, 30, 31 of Phase 4 specification.
"""

from collections import deque
from datetime import datetime, timezone
import json
from queue import Queue, Empty, Full
import threading
import time
from typing import Dict, List, Optional, Tuple, Any, Callable
import uuid

from shared.schemas.v1.models import (
    EventPrediction,
    Event,
    EventStatus,
    EventSeverity,
    Observation,
)
from services.hub_backend.config import settings
from services.hub_backend.database.connection import db_session

from .confidence import ConfidenceFilter
from .debouncer import TemporalDebouncer
from .state_machine import EventStateMachine, InvalidStateTransitionError
from .aggregator import PredictionAggregator
from .zones import ZoneEngine
from .rules import RuleEngine
from .severity import SeverityCalculator
from .lifecycle import generate_event_explanation
from .actions import ActionDispatcher, ActionContext
from .recorder import RecordingManager
from .cooldown import CooldownManager


class EventEngine:
    """
    Central Event & Decision Intelligence Engine.
    Executes asynchronously in a dedicated worker thread with non-blocking queues,
    strictly isolating perception from event reasoning.
    """

    def __init__(
        self,
        confidence_filter: Optional[ConfidenceFilter] = None,
        debouncer: Optional[TemporalDebouncer] = None,
        aggregator: Optional[PredictionAggregator] = None,
        zone_engine: Optional[ZoneEngine] = None,
        rule_engine: Optional[RuleEngine] = None,
        severity_calc: Optional[SeverityCalculator] = None,
        recording_manager: Optional[RecordingManager] = None,
    ):
        self.confidence_filter = confidence_filter or ConfidenceFilter()
        self.debouncer = debouncer or TemporalDebouncer(
            min_consecutive=settings.EVENT_DEFAULT_CONSECUTIVE,
            resolution_timeout_seconds=settings.EVENT_RESOLUTION_TIMEOUT_SECONDS,
        )
        self.aggregator = aggregator or PredictionAggregator(event_window_seconds=5.0)
        self.cooldown_mgr = CooldownManager(
            default_cooldown_seconds=settings.EVENT_DEFAULT_COOLDOWN_SECONDS
        )
        self.zone_engine = zone_engine or ZoneEngine(
            default_loitering_seconds=settings.LOITERING_DEFAULT_DWELL_SECONDS
        )
        self.rule_engine = rule_engine or RuleEngine(cooldown_manager=self.cooldown_mgr)
        self.severity_calc = severity_calc or SeverityCalculator()
        self.recording_mgr = recording_manager or RecordingManager(
            pre_roll_seconds=settings.RECORDING_PRE_ROLL_SECONDS,
            post_roll_seconds=settings.RECORDING_POST_ROLL_SECONDS,
            max_storage_gb=settings.RECORDING_MAX_STORAGE_GB,
            retention_days=settings.RECORDING_RETENTION_DAYS,
        )
        self.action_dispatcher = ActionDispatcher()

        # Bounded asynchronous work queues (Item types: ("pred", pred), ("obs", obs), ("sys", payload))
        self._queue: Queue = Queue(maxsize=1000)
        self.is_running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._sweep_thread: Optional[threading.Thread] = None

        # WebSocket broadcast callbacks: fn(event_type: str, payload: Dict[str, Any])
        self._ws_subscribers: List[Callable[[str, Dict[str, Any]], None]] = []

        # Telemetry metrics
        self._metrics_lock = threading.Lock()
        self._predictions_count = 0
        self._events_created_count = 0
        self._minute_preds: deque = deque()
        self._minute_events: deque = deque()
        self._confirmation_latencies: deque = deque(maxlen=50)

    def subscribe_websocket(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Subscribes an event broadcaster (e.g. WebSocket manager) to lifecycle events."""
        self._ws_subscribers.append(callback)

    def broadcast_ws(self, msg_type: str, data: Dict[str, Any]) -> None:
        for sub in self._ws_subscribers:
            try:
                sub(msg_type, data)
            except Exception as e:
                print(f"[EventEngine] WebSocket broadcast error: {e}")

    def submit_prediction(self, prediction: EventPrediction) -> bool:
        """Non-blocking ingestion entrypoint for SpectatorNet temporal predictions."""
        try:
            self._queue.put_nowait(("pred", prediction))
            return True
        except Full:
            return False

    def submit_observation(self, observation: Observation) -> bool:
        """Non-blocking ingestion entrypoint for spatial observations."""
        try:
            self._queue.put_nowait(("obs", observation))
            return True
        except Full:
            return False

    def submit_system_event(self, camera_id: str, event_type: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """Non-blocking entrypoint for camera state events."""
        try:
            self._queue.put_nowait(("sys", (camera_id, event_type, details or {})))
            return True
        except Full:
            return False

    def start(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        self._sweep_thread = threading.Thread(target=self._sweep_loop, daemon=True)
        self._sweep_thread.start()
        print("[EventEngine] Asynchronous Event Engine started.")

    def stop(self) -> None:
        self.is_running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=1.0)
        if self._sweep_thread:
            self._sweep_thread.join(timeout=1.0)
        print("[EventEngine] Event Engine stopped.")

    def _worker_loop(self) -> None:
        while self.is_running:
            try:
                item_type, payload = self._queue.get(timeout=0.1)
                if item_type == "pred":
                    self._handle_prediction(payload)
                elif item_type == "obs":
                    self._handle_observation(payload)
                elif item_type == "sys":
                    camera_id, ev_type, details = payload
                    self._handle_system_event(camera_id, ev_type, details)
                self._queue.task_done()
            except Empty:
                continue
            except Exception as e:
                print(f"[EventEngine] Error in worker processing loop: {e}")

    def _sweep_loop(self) -> None:
        """Periodically sweeps for inactive active events to resolve them upon timeout."""
        while self.is_running:
            try:
                time.sleep(1.0)
                now = time.time()
                active_events = self.aggregator.get_all_active_events()
                active_keys = [(ev.camera_id, ev.event_type) for ev in active_events if ev.status == EventStatus.ACTIVE]
                
                timed_out = self.debouncer.check_resolution_timeouts(active_keys, now)
                for cam_id, ev_type in timed_out:
                    ev = self.aggregator.get_active_event(cam_id, ev_type)
                    if ev and ev.status == EventStatus.ACTIVE:
                        self.resolve_event(ev.event_id)
            except Exception as e:
                print(f"[EventEngine] Sweep loop error: {e}")

    def _handle_prediction(self, prediction: EventPrediction) -> None:
        """Processes a single SpectatorNet temporal prediction."""
        now = time.time()
        with self._metrics_lock:
            self._predictions_count += 1
            self._minute_preds.append(now)

        # 1. Persist raw prediction to event_predictions table for auditing
        self._persist_prediction(prediction)

        # Skip background class from generating events
        if prediction.event_type == "NORMAL_BACKGROUND":
            return

        # 2. Check Event Cooldown for this camera/event_type
        if self.cooldown_mgr.is_event_in_cooldown(prediction.camera_id, prediction.event_type, now):
            return

        # 3. Confidence Filtering
        if not self.confidence_filter.is_candidate(prediction):
            return

        # 4. Prediction Correlation & Deduplication
        is_existing, existing_event = self.aggregator.correlate(prediction, now)
        if is_existing and existing_event is not None:
            # Active event updated in-memory; persist update
            self._update_persisted_event(existing_event)
            self.broadcast_ws("event_updated", self._event_to_dict(existing_event))
            return

        # 5. Temporal Debouncing (streak requirement)
        is_confirmed, streak = self.debouncer.record_positive_prediction(
            prediction.camera_id, prediction.event_type, now
        )
        if not is_confirmed:
            return  # Needs more consecutive predictions to confirm

        # 6. Event Confirmation: Measure confirmation latency
        streak_start = self.debouncer.get_streak_start_time(prediction.camera_id, prediction.event_type) or now
        latency_ms = (now - streak_start) * 1000.0
        with self._metrics_lock:
            self._confirmation_latencies.append(latency_ms)

        # 7. Match User Rules
        matched_rules = self.rule_engine.match_rules(
            camera_id=prediction.camera_id,
            event_type=prediction.event_type,
            confidence=prediction.confidence,
            zone_id=prediction.metadata.get("zone_id"),
            event_time=prediction.timestamp,
        )

        # 8. Determine Actions & Severity
        severity_override = None
        rule_id = None
        actions_to_execute = {"CREATE_EVENT", "SAVE_CLIP", "CLIENT_NOTIFICATION", "LOG_EVENT"}

        if matched_rules:
            # Aggregate actions from matching rules
            rule_id = matched_rules[0][0].rule_id
            rule_actions = set()
            for r, acts in matched_rules:
                rule_actions.update(acts)
                if r.severity_override:
                    severity_override = r.severity_override
            if rule_actions:
                actions_to_execute = rule_actions

        severity = self.severity_calc.calculate(
            event_type=prediction.event_type,
            confidence=prediction.confidence,
            rule_override=severity_override,
        )

        # 9. Build and Confirm Event
        event_id = f"ev_{uuid.uuid4().hex[:12]}"
        now_dt = datetime.now(timezone.utc)
        start_time = prediction.start_time or now_dt
        end_time = prediction.end_time or now_dt

        explanation = generate_event_explanation(
            event_type=prediction.event_type,
            confidence=prediction.confidence,
            camera_name=prediction.camera_id,
            zone_name=prediction.metadata.get("zone_name"),
            affected_tracks=prediction.affected_tracks,
            metadata=prediction.metadata,
        )

        event = Event(
            event_id=event_id,
            camera_id=prediction.camera_id,
            event_type=prediction.event_type,
            status=EventStatus.CONFIRMED,
            severity=severity,
            confidence=prediction.confidence,
            summary=explanation,
            timestamp=now_dt,
            start_time=start_time,
            end_time=end_time,
            created_at=now_dt,
            updated_at=now_dt,
            involved_track_ids=prediction.affected_tracks,
            zone_id=prediction.metadata.get("zone_id"),
            rule_id=rule_id,
            explanation=explanation,
            metadata={
                "model_version": prediction.metadata.get("model", "spectatornet_v1"),
                "prediction_streak": streak,
                "confirmation_latency_ms": round(latency_ms, 2),
            },
        )

        # Register in Aggregator as active event
        self.aggregator.register_active_event(event)

        # Set event cooldown to avoid spamming
        self.cooldown_mgr.trigger_event_cooldown(
            prediction.camera_id, prediction.event_type, duration=settings.EVENT_DEFAULT_COOLDOWN_SECONDS, now=now
        )

        with self._metrics_lock:
            self._events_created_count += 1
            self._minute_events.append(now)

        # 10. Transition to ACTIVE
        event.status = EventStateMachine.transition(event.status, EventStatus.ACTIVE)

        # 11. Dispatch Actions
        action_ctx = ActionContext(
            event=event,
            rule_id=rule_id,
            recorder_fn=self._trigger_recording,
            websocket_broadcast_fn=self.broadcast_ws,
        )

        for act_name in actions_to_execute:
            self.action_dispatcher.dispatch(act_name, action_ctx)

        self.broadcast_ws("event_created", self._event_to_dict(event))

    def _handle_observation(self, observation: Observation) -> None:
        """Evaluates zone intrusions and loitering from spatial observations."""
        spatial_events = self.zone_engine.process_observation(observation)
        for sev in spatial_events:
            if sev["type"] == "ZONE_LOITERING":
                # Synthesize a high-confidence ZONE_LOITERING EventPrediction
                pred = EventPrediction(
                    schema_version="1.0",
                    camera_id=observation.camera_id,
                    timestamp=observation.timestamp,
                    event_type="ZONE_LOITERING",
                    confidence=0.92,
                    start_time=observation.timestamp,
                    end_time=observation.timestamp,
                    affected_tracks=[sev["track_id"]],
                    class_probabilities={"ZONE_LOITERING": 0.92},
                    sequence_length=30,
                    metadata={
                        "zone_id": sev["zone_id"],
                        "zone_name": sev["zone_name"],
                        "dwell_seconds": sev["dwell_seconds"],
                        "model": "spatial_zone_engine",
                    },
                )
                self._handle_prediction(pred)

    def _handle_system_event(self, camera_id: str, event_type: str, details: Dict[str, Any]) -> None:
        """Processes hardware/connectivity system state events."""
        now_dt = datetime.now(timezone.utc)
        event_id = f"sys_{uuid.uuid4().hex[:12]}"
        sev = self.severity_calc.calculate(event_type, 1.0)
        explanation = generate_event_explanation(event_type, 1.0, camera_id, metadata=details)

        event = Event(
            event_id=event_id,
            camera_id=camera_id,
            event_type=event_type,
            status=EventStatus.CONFIRMED,
            severity=sev,
            confidence=1.0,
            summary=explanation,
            timestamp=now_dt,
            start_time=now_dt,
            end_time=now_dt,
            created_at=now_dt,
            updated_at=now_dt,
            explanation=explanation,
            metadata=details,
        )

        # Transition directly to ACTIVE then RESOLVED if transient
        event.status = EventStatus.ACTIVE
        action_ctx = ActionContext(
            event=event,
            websocket_broadcast_fn=self.broadcast_ws,
        )
        self.action_dispatcher.dispatch("CREATE_EVENT", action_ctx)
        self.action_dispatcher.dispatch("CLIENT_NOTIFICATION", action_ctx)
        self.action_dispatcher.dispatch("LOG_EVENT", action_ctx)
        self.broadcast_ws("system_event", self._event_to_dict(event))

    def _trigger_recording(self, event: Event) -> None:
        """Signals recording manager to start clip capture."""
        self.recording_mgr.trigger_recording_start(event)

    def acknowledge_event(self, event_id: str) -> Event:
        """Marks event acknowledged by user."""
        event = self._get_event_by_id(event_id)
        if not event:
            raise KeyError(f"Event '{event_id}' not found.")
        event.metadata["acknowledged"] = True
        event.metadata["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
        self._update_persisted_event(event)
        self.broadcast_ws("event_updated", self._event_to_dict(event))
        return event

    def dismiss_event(self, event_id: str) -> Event:
        """Dismisses an event, transitioning it to DISMISSED."""
        event = self._get_event_by_id(event_id)
        if not event:
            raise KeyError(f"Event '{event_id}' not found.")

        event.status = EventStateMachine.transition(event.status, EventStatus.DISMISSED)
        event.updated_at = datetime.now(timezone.utc)
        self.aggregator.remove_active_event(event.camera_id, event.event_type)
        self.debouncer.reset_streak(event.camera_id, event.event_type)
        self._update_persisted_event(event)
        self.broadcast_ws("event_updated", self._event_to_dict(event))
        return event

    def resolve_event(self, event_id: str) -> Event:
        """Resolves an active event and finalizes any ongoing recording clip."""
        event = self._get_event_by_id(event_id)
        if not event:
            raise KeyError(f"Event '{event_id}' not found.")

        event.status = EventStateMachine.transition(event.status, EventStatus.RESOLVED)
        now_dt = datetime.now(timezone.utc)
        event.end_time = now_dt
        event.updated_at = now_dt

        # Remove from active correlation
        self.aggregator.remove_active_event(event.camera_id, event.event_type)
        self.debouncer.reset_streak(event.camera_id, event.event_type)

        # Finalize event recording in background
        def finalize_clip():
            rec = self.recording_mgr.finalize_recording(event)
            if rec:
                event.recording_id = rec.recording_id
                self._update_persisted_event(event)
                self.broadcast_ws("recording_created", {
                    "recording_id": rec.recording_id,
                    "event_id": event.event_id,
                    "camera_id": rec.camera_id,
                    "file_path": rec.file_path,
                    "duration_seconds": rec.duration_seconds,
                })

        threading.Thread(target=finalize_clip, daemon=True).start()

        self._update_persisted_event(event)
        self.broadcast_ws("event_resolved", self._event_to_dict(event))
        return event

    def _persist_prediction(self, prediction: EventPrediction) -> None:
        """Inserts raw model prediction into event_predictions table."""
        try:
            with db_session() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO cameras (camera_id, name, source_type, status)
                    VALUES (?, ?, 'phone', 'streaming')
                    """,
                    (prediction.camera_id, f"Camera {prediction.camera_id}"),
                )
                conn.execute(
                    """
                    INSERT INTO event_predictions (
                        prediction_id, camera_id, timestamp, event_type,
                        confidence, affected_tracks, model_version, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"pred_{uuid.uuid4().hex[:12]}",
                        prediction.camera_id,
                        prediction.timestamp.isoformat(),
                        prediction.event_type,
                        prediction.confidence,
                        json.dumps(prediction.affected_tracks),
                        prediction.metadata.get("model", "spectatornet_v1"),
                        json.dumps(prediction.metadata),
                    ),
                )
        except Exception:
            pass

    def _update_persisted_event(self, event: Event) -> None:
        """Updates event record in SQLite database."""
        with db_session() as conn:
            conn.execute(
                """
                UPDATE events SET
                    status = ?,
                    severity = ?,
                    confidence = ?,
                    end_time = ?,
                    updated_at = ?,
                    recording_id = COALESCE(?, recording_id),
                    involved_track_ids = ?,
                    explanation = ?,
                    metadata_json = ?
                WHERE event_id = ?
                """,
                (
                    event.status.value,
                    event.severity.value,
                    event.confidence,
                    event.end_time.isoformat() if event.end_time else None,
                    event.updated_at.isoformat(),
                    event.recording_id,
                    json.dumps(event.involved_track_ids),
                    event.explanation,
                    json.dumps(event.metadata),
                    event.event_id,
                ),
            )

    def _get_event_by_id(self, event_id: str) -> Optional[Event]:
        # Check active in-memory events first
        for ev in self.aggregator.get_all_active_events():
            if ev.event_id == event_id:
                return ev

        # Fallback to SQLite
        with db_session() as conn:
            cursor = conn.execute("SELECT * FROM events WHERE event_id = ?", (event_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_event(row)

    def _row_to_event(self, r: Dict[str, Any]) -> Event:
        tracks = json.loads(r["involved_track_ids"]) if r.get("involved_track_ids") else []
        meta = json.loads(r["metadata_json"]) if r.get("metadata_json") else {}
        return Event(
            event_id=r["event_id"],
            camera_id=r["camera_id"],
            task_id=r.get("task_id"),
            recording_id=r.get("recording_id"),
            event_type=r["event_type"],
            status=EventStatus(r.get("status", "detected")),
            severity=EventSeverity(r["severity"]),
            confidence=r["confidence"],
            summary=r["summary"],
            timestamp=datetime.fromisoformat(r["timestamp"]),
            start_time=datetime.fromisoformat(r["start_time"]) if r.get("start_time") else None,
            end_time=datetime.fromisoformat(r["end_time"]) if r.get("end_time") else None,
            created_at=datetime.fromisoformat(r["created_at"]) if r.get("created_at") else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(r["updated_at"]) if r.get("updated_at") else datetime.now(timezone.utc),
            involved_track_ids=tracks,
            zone_id=r.get("zone_id"),
            rule_id=r.get("rule_id"),
            explanation=r.get("explanation"),
            metadata=meta,
        )

    def _event_to_dict(self, ev: Event) -> Dict[str, Any]:
        return {
            "event_id": ev.event_id,
            "camera_id": ev.camera_id,
            "event_type": ev.event_type,
            "status": ev.status.value,
            "severity": ev.severity.value,
            "confidence": ev.confidence,
            "summary": ev.summary,
            "explanation": ev.explanation,
            "timestamp": ev.timestamp.isoformat(),
            "start_time": ev.start_time.isoformat() if ev.start_time else None,
            "end_time": ev.end_time.isoformat() if ev.end_time else None,
            "involved_track_ids": ev.involved_track_ids,
            "zone_id": ev.zone_id,
            "rule_id": ev.rule_id,
            "recording_id": ev.recording_id,
            "metadata": ev.metadata,
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Calculates real-time observability metrics without fabricating performance."""
        now = time.time()
        with self._metrics_lock:
            # Purge entries older than 60s
            while self._minute_preds and self._minute_preds[0] < now - 60.0:
                self._minute_preds.popleft()
            while self._minute_events and self._minute_events[0] < now - 60.0:
                self._minute_events.popleft()

            preds_per_min = len(self._minute_preds)
            events_per_min = len(self._minute_events)
            active_events = len(self.aggregator.get_all_active_events())
            mean_latency = (
                sum(self._confirmation_latencies) / len(self._confirmation_latencies)
                if self._confirmation_latencies
                else 0.0
            )

        return {
            "predictions_per_minute": preds_per_min,
            "events_per_minute": events_per_min,
            "active_events_count": active_events,
            "queue_depth": self._queue.qsize(),
            "mean_confirmation_latency_ms": round(mean_latency, 2),
            "total_predictions_processed": self._predictions_count,
            "total_events_created": self._events_created_count,
            "engine_status": "running" if self.is_running else "stopped",
        }

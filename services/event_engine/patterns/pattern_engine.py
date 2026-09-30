"""
Smart Spectator - Temporal Pattern Engine
Conforms to Section 10 of Phase 10 Specification.
Identifies recurring temporal patterns and event clustering locally.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
import json
import logging
from typing import Dict, Any, List, Optional
import uuid

from services.hub_backend.database.connection import get_db

logger = logging.getLogger("PatternEngine")


@dataclass
class EventPattern:
    pattern_id: str
    pattern_type: str
    event_types: List[str]
    time_window_seconds: float
    frequency: int
    confidence: float
    first_seen: str
    last_seen: str
    camera_id: Optional[str] = None
    zone_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TemporalPatternEngine:
    """
    Discovers recurring patterns over time windows (e.g. repeated entry,
    recurring loitering clusters). Zero cloud or external dependencies.
    """

    def scan_for_patterns(
        self,
        camera_id: Optional[str] = None,
        window_minutes: int = 60,
        min_frequency: int = 3,
        persist: bool = True,
    ) -> List[EventPattern]:
        since_time = (datetime.now(timezone.utc) - timedelta(minutes=window_minutes)).isoformat()
        query = """
        SELECT event_id, event_type, camera_id, zone_id, timestamp, confidence
        FROM events
        WHERE timestamp >= ?
        """
        params: List[Any] = [since_time]
        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        query += " ORDER BY timestamp ASC"

        with get_db() as conn:
            cursor = conn.execute(query, tuple(params))
            events = cursor.fetchall()

        if not events:
            return []

        # Cluster by (camera_id, zone_id, event_type)
        clusters: Dict[tuple, List[Any]] = {}
        for ev in events:
            cam = ev[2] if not isinstance(ev, dict) else ev["camera_id"]
            zn = ev[3] if not isinstance(ev, dict) else ev["zone_id"]
            ev_type = ev[1] if not isinstance(ev, dict) else ev["event_type"]
            key = (cam, zn, ev_type)
            if key not in clusters:
                clusters[key] = []
            clusters[key].append(ev)

        patterns: List[EventPattern] = []
        for (cam, zn, ev_type), cluster_events in clusters.items():
            freq = len(cluster_events)
            if freq >= min_frequency:
                first_ts = cluster_events[0][4] if not isinstance(cluster_events[0], dict) else cluster_events[0]["timestamp"]
                last_ts = cluster_events[-1][4] if not isinstance(cluster_events[-1], dict) else cluster_events[-1]["timestamp"]
                
                # Mean confidence
                confs = [e[5] if not isinstance(e, dict) else e["confidence"] for e in cluster_events]
                avg_conf = round(sum(confs) / max(1, len(confs)), 3)

                pat_id = f"pat_{uuid.uuid4().hex[:12]}"
                pattern = EventPattern(
                    pattern_id=pat_id,
                    pattern_type="REPEATED_ACTIVITY",
                    event_types=[ev_type],
                    time_window_seconds=window_minutes * 60.0,
                    frequency=freq,
                    confidence=avg_conf,
                    first_seen=first_ts,
                    last_seen=last_ts,
                    camera_id=cam,
                    zone_id=zn,
                    metadata={"sample_event_count": freq, "analyzed_window_min": window_minutes},
                )
                patterns.append(pattern)

        if persist and patterns:
            self._save_patterns(patterns)

        return patterns

    def _save_patterns(self, patterns: List[EventPattern]) -> None:
        try:
            with get_db() as conn:
                for p in patterns:
                    conn.execute(
                        """
                        INSERT INTO event_patterns (
                            pattern_id, pattern_type, event_types_json, camera_id,
                            zone_id, frequency, time_window_seconds, confidence,
                            first_seen, last_seen, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            p.pattern_id,
                            p.pattern_type,
                            json.dumps(p.event_types),
                            p.camera_id,
                            p.zone_id,
                            p.frequency,
                            p.time_window_seconds,
                            p.confidence,
                            p.first_seen,
                            p.last_seen,
                            json.dumps(p.metadata),
                        ),
                    )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist patterns: {e}")

    def list_patterns(self, camera_id: Optional[str] = None, limit: int = 50) -> List[EventPattern]:
        query = "SELECT * FROM event_patterns WHERE 1=1"
        params: List[Any] = []
        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        query += " ORDER BY last_seen DESC LIMIT ?"
        params.append(limit)

        with get_db() as conn:
            cursor = conn.execute(query, tuple(params))
            rows = cursor.fetchall()
            cols = [col[0] for col in cursor.description]
            results = []
            for r in rows:
                d = dict(zip(cols, r)) if not isinstance(r, dict) else r
                results.append(
                    EventPattern(
                        pattern_id=d["pattern_id"],
                        pattern_type=d["pattern_type"],
                        event_types=json.loads(d["event_types_json"] or "[]"),
                        time_window_seconds=float(d["time_window_seconds"]),
                        frequency=int(d["frequency"]),
                        confidence=float(d["confidence"]),
                        first_seen=d["first_seen"],
                        last_seen=d["last_seen"],
                        camera_id=d.get("camera_id"),
                        zone_id=d.get("zone_id"),
                        metadata=json.loads(d.get("metadata_json") or "{}"),
                    )
                )
            return results


pattern_engine = TemporalPatternEngine()

"""
Smart Spectator - Event Engine: Spatial Zone System & Loitering Detection
Evaluates object centroids within normalized polygon regions of interest (ROI).
Conforms to Sections 13, 14, 15, 21 of Phase 4 specification.
"""

from datetime import datetime, timezone
import json
import time
from typing import List, Dict, Tuple, Optional, Any, Set
import sqlite3

from shared.schemas.v1.models import Zone, Observation, TrackedObject, EventPrediction
from services.hub_backend.database.connection import db_session


def point_inside_polygon(point: Tuple[float, float], polygon: List[List[float]]) -> bool:
    """
    Ray-casting algorithm to test if normalized point (x, y) is inside polygon.
    Polygon is a list of [x, y] coordinates in normalized range [0.0, 1.0].
    """
    x, y = point
    n = len(polygon)
    if n < 3:
        return False

    inside = False
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        # Check if point is on horizontal edge or vertex
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


def compute_centroid(bbox_xyxy: List[float]) -> Tuple[float, float]:
    """Computes centroid (cx, cy) from normalized [x1, y1, x2, y2] bounding box."""
    cx = (bbox_xyxy[0] + bbox_xyxy[2]) / 2.0
    cy = (bbox_xyxy[1] + bbox_xyxy[3]) / 2.0
    return cx, cy


class TrackZoneState:
    """Tracks temporal state of a tracked object relative to a specific zone."""

    def __init__(self, track_id: int, camera_id: str, zone_id: str, entry_time: float):
        self.track_id = track_id
        self.camera_id = camera_id
        self.zone_id = zone_id
        self.entry_time = entry_time
        self.last_seen_time = entry_time
        self.loitering_alerted = False

    @property
    def dwell_time_seconds(self) -> float:
        return max(0.0, self.last_seen_time - self.entry_time)


class ZoneEngine:
    """
    Spatial Analysis Engine.
    Maintains camera-local zones, monitors track entries/exits/dwell times,
    and detects zone loitering events.
    """

    def __init__(self, default_loitering_seconds: float = 30.0):
        self.default_loitering_seconds = default_loitering_seconds
        # Key: camera_id -> Dict[zone_id, Zone]
        self._zones: Dict[str, Dict[str, Zone]] = {}
        # Key: (camera_id, zone_id, track_id) -> TrackZoneState
        self._occupancy: Dict[Tuple[str, str, int], TrackZoneState] = {}
        self.load_zones_from_db()

    def load_zones_from_db(self) -> None:
        """Loads all active zones from SQLite persistence into memory."""
        try:
            with db_session() as conn:
                cursor = conn.execute(
                    "SELECT zone_id, camera_id, name, polygon_json, color, is_active, created_at, updated_at "
                    "FROM zones WHERE is_active = 1"
                )
                rows = cursor.fetchall()
                self._zones.clear()
                for r in rows:
                    poly = json.loads(r["polygon_json"])
                    zone = Zone(
                        zone_id=r["zone_id"],
                        camera_id=r["camera_id"],
                        name=r["name"],
                        polygon=poly,
                        color=r.get("color", "#38bdf8"),
                        is_active=bool(r["is_active"]),
                        created_at=datetime.fromisoformat(r["created_at"]) if isinstance(r["created_at"], str) else r["created_at"],
                        updated_at=datetime.fromisoformat(r["updated_at"]) if isinstance(r["updated_at"], str) else r["updated_at"],
                    )
                    self.add_or_update_zone_memory(zone)
        except Exception as e:
            print(f"[ZoneEngine] Database load note: {e}")

    def add_or_update_zone_memory(self, zone: Zone) -> None:
        if zone.camera_id not in self._zones:
            self._zones[zone.camera_id] = {}
        self._zones[zone.camera_id][zone.zone_id] = zone

    def remove_zone_memory(self, camera_id: str, zone_id: str) -> None:
        if camera_id in self._zones:
            self._zones[camera_id].pop(zone_id, None)
        # Clean up occupancy records for this zone
        to_remove = [k for k in self._occupancy.keys() if k[0] == camera_id and k[1] == zone_id]
        for k in to_remove:
            self._occupancy.pop(k, None)

    def get_zones_for_camera(self, camera_id: str) -> List[Zone]:
        return list(self._zones.get(camera_id, {}).values())

    def get_zone(self, camera_id: str, zone_id: str) -> Optional[Zone]:
        return self._zones.get(camera_id, {}).get(zone_id)

    def validate_polygon(self, polygon: List[List[float]]) -> None:
        """Validates normalized polygon coordinates and shape."""
        if len(polygon) < 3:
            raise ValueError("Polygon must contain at least 3 vertices.")
        for pt in polygon:
            if len(pt) != 2:
                raise ValueError("Polygon vertex must be a 2D coordinate [x, y].")
            x, y = pt
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise ValueError(f"Coordinate ({x}, {y}) outside normalized bounds [0.0, 1.0].")

    def process_observation(
        self, observation: Observation, loitering_threshold_seconds: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Evaluates current observation against camera zones.
        Detects entries, exits, dwell updates, and loitering triggers.
        Returns list of spatial events (e.g. entry, exit, loitering).
        """
        camera_id = observation.camera_id
        zones = self._zones.get(camera_id, {})
        if not zones:
            return []

        now_ts = observation.timestamp.replace(tzinfo=timezone.utc).timestamp()
        threshold = loitering_threshold_seconds or self.default_loitering_seconds
        events_emitted = []

        # Find which tracks are inside which zones in this observation
        active_in_zones: Set[Tuple[str, int]] = set() # (zone_id, track_id)

        for track in observation.tracked_objects:
            if not track.is_active or not track.current_bbox:
                continue
            centroid = compute_centroid(track.current_bbox)

            for zone_id, zone in zones.items():
                if not zone.is_active:
                    continue

                if point_inside_polygon(centroid, zone.polygon):
                    active_in_zones.add((zone_id, track.track_id))
                    occ_key = (camera_id, zone_id, track.track_id)

                    if occ_key not in self._occupancy:
                        # Newly entered zone
                        state = TrackZoneState(track.track_id, camera_id, zone_id, now_ts)
                        self._occupancy[occ_key] = state
                        events_emitted.append({
                            "type": "ZONE_ENTER",
                            "camera_id": camera_id,
                            "zone_id": zone_id,
                            "zone_name": zone.name,
                            "track_id": track.track_id,
                            "class_name": track.class_name,
                            "centroid": centroid,
                            "timestamp": observation.timestamp,
                        })
                    else:
                        # Remained in zone: update dwell time
                        state = self._occupancy[occ_key]
                        state.last_seen_time = now_ts
                        dwell = state.dwell_time_seconds

                        # Check for loitering (typically applies to persons)
                        if (
                            dwell >= threshold
                            and track.class_name.lower() in ("person", "human")
                        ):
                            state.loitering_alerted = True
                            events_emitted.append({
                                "type": "ZONE_LOITERING",
                                "camera_id": camera_id,
                                "zone_id": zone_id,
                                "zone_name": zone.name,
                                "track_id": track.track_id,
                                "class_name": track.class_name,
                                "dwell_seconds": round(dwell, 1),
                                "centroid": centroid,
                                "timestamp": observation.timestamp,
                            })

        # Check for tracks that exited zones
        for (cam, zid, tid), state in list(self._occupancy.items()):
            if cam == camera_id:
                if (zid, tid) not in active_in_zones:
                    # Track is no longer in zone (or disappeared)
                    # Allow brief 1-second grace period before marking exit
                    if now_ts - state.last_seen_time > 1.0:
                        zone = zones.get(zid)
                        events_emitted.append({
                            "type": "ZONE_EXIT",
                            "camera_id": camera_id,
                            "zone_id": zid,
                            "zone_name": zone.name if zone else zid,
                            "track_id": tid,
                            "total_dwell_seconds": round(state.dwell_time_seconds, 1),
                            "timestamp": observation.timestamp,
                        })
                        del self._occupancy[(cam, zid, tid)]

        return events_emitted

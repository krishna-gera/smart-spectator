"""
Smart Spectator - Level 2 ByteTrack Multi-Object Tracker
Conforms to shared/protocols/ai_models.py and shared/schemas/v1/models.py
Maintains persistent track IDs, velocity vectors, and trajectory history.
"""

from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional
import numpy as np
from scipy.optimize import linear_sum_assignment

from shared.protocols.ai_models import ObjectTracker
from shared.schemas.v1.models import Detection, TrackedObject


def calculate_iou(box1: List[float], box2: List[float]) -> float:
    """Calculates Intersection-over-Union (IoU) between two [x1, y1, x2, y2] boxes."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter_area = inter_w * inter_h

    area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])
    union_area = area1 + area2 - inter_area

    if union_area <= 0:
        return 0.0
    return inter_area / union_area


class SingleTrack:
    """Represents a single tracked target object over time."""

    def __init__(self, track_id: int, camera_id: str, detection: Detection, timestamp: datetime):
        self.track_id = track_id
        self.camera_id = camera_id
        self.class_name = detection.class_name
        self.current_bbox = list(detection.bbox_xyxy)
        self.confidence = detection.confidence
        self.first_seen = timestamp
        self.last_seen = timestamp
        
        # Centroid trajectory
        cx = (self.current_bbox[0] + self.current_bbox[2]) / 2.0
        cy = (self.current_bbox[1] + self.current_bbox[3]) / 2.0
        self.trajectory: List[List[float]] = [[round(cx, 4), round(cy, 4)]]
        self.velocity: List[float] = [0.0, 0.0]
        
        self.time_since_update = 0
        self.hits = 1
        self.is_active = True

    def update(self, detection: Detection, timestamp: datetime):
        new_bbox = list(detection.bbox_xyxy)
        new_cx = (new_bbox[0] + new_bbox[2]) / 2.0
        new_cy = (new_bbox[1] + new_bbox[3]) / 2.0
        
        # Compute velocity delta (normalized px / update)
        prev_cx, prev_cy = self.trajectory[-1]
        vx = round(new_cx - prev_cx, 4)
        vy = round(new_cy - prev_cy, 4)
        self.velocity = [vx, vy]

        self.current_bbox = new_bbox
        self.confidence = detection.confidence
        self.last_seen = timestamp
        self.trajectory.append([round(new_cx, 4), round(new_cy, 4)])
        if len(self.trajectory) > 50:
            self.trajectory.pop(0)

        self.hits += 1
        self.time_since_update = 0
        self.is_active = True

    def mark_missed(self):
        self.time_since_update += 1
        if self.time_since_update > 2:
            self.is_active = False

    def to_schema(self) -> TrackedObject:
        return TrackedObject(
            track_id=self.track_id,
            camera_id=self.camera_id,
            class_name=self.class_name,
            current_bbox=self.current_bbox,
            velocity_vector=self.velocity,
            first_seen_timestamp=self.first_seen,
            last_seen_timestamp=self.last_seen,
            trajectory=list(self.trajectory),
            confidence=round(self.confidence, 3),
            is_active=self.is_active
        )


class ByteTrackTracker(ObjectTracker):
    """
    Two-stage Bipartite Matching ByteTrack Tracker.
    Maintains persistent tracklet identities without deep Re-ID neural networks.
    """

    def __init__(
        self,
        high_conf_threshold: float = 0.5,
        match_iou_threshold: float = 0.3,
        max_age_frames: int = 30 # Retain lost tracks for ~6s at 5 FPS
    ):
        self.high_conf_threshold = high_conf_threshold
        self.match_iou_threshold = match_iou_threshold
        self.max_age_frames = max_age_frames
        
        self.next_track_id = 1
        self.tracks: List[SingleTrack] = []

    def update(self, camera_id: str, detections: List[Detection], timestamp: Optional[float] = None) -> List[TrackedObject]:
        ts = datetime.now(timezone.utc)
        
        # Partition detections into High-confidence (D_high) and Low-confidence (D_low)
        d_high: List[Detection] = []
        d_low: List[Detection] = []
        for d in detections:
            if d.confidence >= self.high_conf_threshold:
                d_high.append(d)
            else:
                d_low.append(d)

        # 1. Match active tracks with D_high
        unmatched_tracks, unmatched_d_high = self._match_tracks_to_detections(
            self.tracks, d_high, ts
        )

        # 2. Match remaining tracks with D_low (recovering occlusions/blur)
        still_unmatched_tracks, _ = self._match_tracks_to_detections(
            unmatched_tracks, d_low, ts
        )

        # 3. Initialize new tracks for unmatched high-confidence detections
        for det in unmatched_d_high:
            new_track = SingleTrack(self.next_track_id, camera_id, det, ts)
            self.next_track_id += 1
            self.tracks.append(new_track)

        # 4. Mark unassociated tracks as missed & purge dead tracks
        for t in still_unmatched_tracks:
            t.mark_missed()

        self.tracks = [t for t in self.tracks if t.time_since_update <= self.max_age_frames]

        # Return standardized TrackedObject list
        return [t.to_schema() for t in self.tracks]

    def _match_tracks_to_detections(
        self,
        tracks: List[SingleTrack],
        dets: List[Detection],
        timestamp: datetime
    ) -> Tuple[List[SingleTrack], List[Detection]]:
        if not tracks or not dets:
            return list(tracks), list(dets)

        # Construct IoU cost matrix
        cost_matrix = np.zeros((len(tracks), len(dets)), dtype=np.float32)
        for i, t in enumerate(tracks):
            for j, d in enumerate(dets):
                # Prefer same class matching
                class_penalty = 0.0 if t.class_name == d.class_name else 0.5
                iou = calculate_iou(t.current_bbox, d.bbox_xyxy)
                cost_matrix[i, j] = 1.0 - max(0.0, iou - class_penalty)

        row_indices, col_indices = linear_sum_assignment(cost_matrix)

        matched_tracks = set()
        matched_dets = set()

        for r, c in zip(row_indices, col_indices):
            if cost_matrix[r, c] < (1.0 - self.match_iou_threshold):
                tracks[r].update(dets[c], timestamp)
                matched_tracks.add(r)
                matched_dets.add(c)

        unmatched_tracks = [tracks[i] for i in range(len(tracks)) if i not in matched_tracks]
        unmatched_dets = [dets[j] for j in range(len(dets)) if j not in matched_dets]

        return unmatched_tracks, unmatched_dets

    def reset(self, camera_id: Optional[str] = None) -> None:
        if camera_id:
            self.tracks = [t for t in self.tracks if t.camera_id != camera_id]
        else:
            self.tracks.clear()
            self.next_track_id = 1

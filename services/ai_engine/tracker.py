"""
Smart Spectator - Level 2 ByteTrack Multi-Object Tracker
Conforms to shared/protocols/ai_models.py and shared/schemas/v1/models.py
Maintains persistent track IDs, Kalman filter state, velocity vectors, and trajectory history.
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


class KalmanBoxFilter:
    """
    Constant Velocity Linear Kalman Filter for Bounding Box Tracking.
    State vector: [cx, cy, w, h, vx, vy, vw, vh]^T in R^8.
    Measurement vector: [cx, cy, w, h]^T in R^4.
    """

    def __init__(self, bbox_xyxy: List[float]):
        x1, y1, x2, y2 = bbox_xyxy
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        w = max(1e-4, x2 - x1)
        h = max(1e-4, y2 - y1)

        # State transition matrix F (8x8)
        self.F = np.eye(8, dtype=np.float32)
        for i in range(4):
            self.F[i, i + 4] = 1.0  # x_{t+1} = x_t + v_t * dt

        # Measurement matrix H (4x8)
        self.H = np.zeros((4, 8), dtype=np.float32)
        for i in range(4):
            self.H[i, i] = 1.0

        # State mean vector
        self.mean = np.array([cx, cy, w, h, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)

        # Process noise covariance Q
        self.Q = np.eye(8, dtype=np.float32) * 1e-2
        self.Q[4:, 4:] *= 1e-1

        # Measurement noise covariance R
        self.R = np.eye(4, dtype=np.float32) * 1e-3

        # State covariance P
        self.P = np.eye(8, dtype=np.float32) * 10.0
        self.P[4:, 4:] *= 100.0

    def predict(self) -> List[float]:
        """Projects state and covariance forward by 1 time step."""
        self.mean = np.dot(self.F, self.mean)
        self.P = np.dot(np.dot(self.F, self.P), self.F.T) + self.Q
        return self.get_bbox_xyxy()

    def update(self, bbox_xyxy: List[float]):
        """Corrects state estimate with measured bounding box."""
        x1, y1, x2, y2 = bbox_xyxy
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        w = max(1e-4, x2 - x1)
        h = max(1e-4, y2 - y1)
        z = np.array([cx, cy, w, h], dtype=np.float32)

        y = z - np.dot(self.H, self.mean)
        S = np.dot(np.dot(self.H, self.P), self.H.T) + self.R
        K = np.dot(np.dot(self.P, self.H.T), np.linalg.inv(S))

        self.mean = self.mean + np.dot(K, y)
        I = np.eye(8, dtype=np.float32)
        self.P = np.dot(I - np.dot(K, self.H), self.P)

    def get_bbox_xyxy(self) -> List[float]:
        cx, cy, w, h = self.mean[:4]
        x1 = max(0.0, cx - w / 2.0)
        y1 = max(0.0, cy - h / 2.0)
        x2 = min(1.0, cx + w / 2.0)
        y2 = min(1.0, cy + h / 2.0)
        return [float(round(x1, 4)), float(round(y1, 4)), float(round(x2, 4)), float(round(y2, 4))]

    @property
    def velocity(self) -> List[float]:
        return [float(round(self.mean[4], 4)), float(round(self.mean[5], 4))]


class SingleTrack:
    """Represents a single tracked target object over time with Kalman filtering."""

    def __init__(self, track_id: int, camera_id: str, detection: Detection, timestamp: datetime):
        self.track_id = track_id
        self.camera_id = camera_id
        self.class_name = detection.class_name
        self.current_bbox = list(detection.bbox_xyxy)
        self.confidence = detection.confidence
        self.first_seen = timestamp
        self.last_seen = timestamp

        # Initialize Kalman Filter
        self.kf = KalmanBoxFilter(self.current_bbox)
        self.velocity = self.kf.velocity

        cx = (self.current_bbox[0] + self.current_bbox[2]) / 2.0
        cy = (self.current_bbox[1] + self.current_bbox[3]) / 2.0
        self.trajectory: List[List[float]] = [[round(cx, 4), round(cy, 4)]]

        self.time_since_update = 0
        self.hits = 1
        self.is_active = True

    def predict(self) -> List[float]:
        """Advances track state using Kalman motion model."""
        predicted_bbox = self.kf.predict()
        self.current_bbox = predicted_bbox
        self.velocity = self.kf.velocity
        return predicted_bbox

    def update(self, detection: Detection, timestamp: datetime):
        """Updates track with a matched detection and corrects Kalman state."""
        self.kf.update(detection.bbox_xyxy)
        self.current_bbox = list(detection.bbox_xyxy)  # Use detection bbox for ground truth position
        self.velocity = self.kf.velocity
        self.confidence = detection.confidence
        self.last_seen = timestamp

        cx = (self.current_bbox[0] + self.current_bbox[2]) / 2.0
        cy = (self.current_bbox[1] + self.current_bbox[3]) / 2.0
        self.trajectory.append([round(cx, 4), round(cy, 4)])
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
            is_active=self.is_active,
        )


class ByteTrackTracker(ObjectTracker):
    """
    Two-stage Bipartite Matching ByteTrack Tracker with Kalman Filter Motion Prediction.
    Maintains persistent tracklet identities without deep Re-ID neural networks.
    """

    def __init__(
        self,
        high_conf_threshold: float = 0.5,
        match_iou_threshold: float = 0.3,
        max_age_frames: int = 30,  # Retain lost tracks for ~6s at 5 FPS
    ):
        self.high_conf_threshold = high_conf_threshold
        self.match_iou_threshold = match_iou_threshold
        self.max_age_frames = max_age_frames

        self.next_track_id = 1
        self.tracks: List[SingleTrack] = []

    def update(
        self, camera_id: str, detections: List[Detection], timestamp: Optional[float] = None
    ) -> List[TrackedObject]:
        ts = datetime.now(timezone.utc)

        # 0. Predict new locations of existing tracks with Kalman filter
        for track in self.tracks:
            track.predict()

        # Partition detections into High-confidence (D_high) and Low-confidence (D_low)
        d_high: List[Detection] = []
        d_low: List[Detection] = []
        for d in detections:
            if d.confidence >= self.high_conf_threshold:
                d_high.append(d)
            else:
                d_low.append(d)

        # 1. Match predicted tracks with D_high
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
        self, tracks: List[SingleTrack], dets: List[Detection], timestamp: datetime
    ) -> Tuple[List[SingleTrack], List[Detection]]:
        if not tracks or not dets:
            return list(tracks), list(dets)

        # Construct IoU cost matrix using predicted track boxes
        cost_matrix = np.zeros((len(tracks), len(dets)), dtype=np.float32)
        for i, t in enumerate(tracks):
            for j, d in enumerate(dets):
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

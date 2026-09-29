"""
Smart Spectator - Synthetic Observation Sequence Generator
Generates realistic multi-timestep Observation sequences for all 9 event classes.
Used for CI, training pipeline verification, and bootstrapping before large-scale recordings.
Strictly tags source_type = "synthetic".
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple
import random
import uuid

from shared.schemas.v1.models import Observation, Detection, TrackedObject
from .schema import SequenceSample, TemporalAnnotation
from .constants import DEFAULT_EVENT_CLASSES, CLASS_TO_ID, DEFAULT_SEQUENCE_LENGTH, DEFAULT_SAMPLING_RATE_FPS


class SyntheticSequenceGenerator:
    """Generates synthetic observation sequences with realistic object kinematics and transitions."""

    def __init__(self, sequence_length: int = DEFAULT_SEQUENCE_LENGTH, fps: float = DEFAULT_SAMPLING_RATE_FPS, seed: int = 42):
        self.sequence_length = sequence_length
        self.fps = fps
        self.time_delta_sec = 1.0 / fps
        self.rng = random.Random(seed)

    def generate_sample(
        self,
        event_class: str,
        session_id: str,
        camera_id: str = "cam_synthetic_01",
    ) -> SequenceSample:
        """Generates a single 30-frame sequence for the designated event class."""
        assert event_class in DEFAULT_EVENT_CLASSES, f"Unknown class {event_class}"
        sample_id = f"syn_{session_id}_{event_class.lower()}_{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc) - timedelta(seconds=self.sequence_length * self.time_delta_sec)

        observations: List[Observation] = []

        # Coordinate templates
        desk_bbox = [0.15, 0.55, 0.85, 0.95]

        # Generate frames based on event type
        for t in range(self.sequence_length):
            frame_ts = now + timedelta(seconds=t * self.time_delta_sec)
            detections: List[Detection] = []
            tracked_objects: List[TrackedObject] = []
            scene_state: Dict[str, Any] = {"motion_detected": False, "scene_type": "desk"}

            if event_class == "NORMAL_BACKGROUND":
                # Static scene: optional stationary desk / chair
                det = Detection(
                    detection_id=f"d_chair_{t}",
                    class_id=56,
                    class_name="chair",
                    confidence=0.92,
                    bbox_xyxy=[0.65, 0.40, 0.88, 0.85],
                )
                track = TrackedObject(
                    track_id=1,
                    camera_id=camera_id,
                    class_name="chair",
                    current_bbox=det.bbox_xyxy,
                    velocity_vector=[0.0, 0.0],
                    first_seen_timestamp=now,
                    last_seen_timestamp=frame_ts,
                    trajectory=[[0.76, 0.62]],
                    confidence=0.92,
                    is_active=True,
                )
                detections.append(det)
                tracked_objects.append(track)

            elif event_class == "OBJECT_PRESENT":
                # Cup remains stationary on desk
                det = Detection(
                    detection_id=f"d_cup_{t}",
                    class_id=41,
                    class_name="cup",
                    confidence=0.94,
                    bbox_xyxy=[0.42, 0.50, 0.49, 0.62],
                )
                track = TrackedObject(
                    track_id=2,
                    camera_id=camera_id,
                    class_name="cup",
                    current_bbox=det.bbox_xyxy,
                    velocity_vector=[0.0, 0.0],
                    first_seen_timestamp=now,
                    last_seen_timestamp=frame_ts,
                    trajectory=[[0.45, 0.56]],
                    confidence=0.94,
                    is_active=True,
                )
                detections.append(det)
                tracked_objects.append(track)

            elif event_class == "OBJECT_REMOVED":
                # Cup is present in frames 0..14, then removed/disappears in frames 15..29
                if t < 15:
                    det = Detection(
                        detection_id=f"d_cup_{t}",
                        class_id=41,
                        class_name="cup",
                        confidence=0.93,
                        bbox_xyxy=[0.42, 0.50, 0.49, 0.62],
                    )
                    track = TrackedObject(
                        track_id=3,
                        camera_id=camera_id,
                        class_name="cup",
                        current_bbox=det.bbox_xyxy,
                        velocity_vector=[0.0, 0.0],
                        first_seen_timestamp=now,
                        last_seen_timestamp=frame_ts,
                        trajectory=[[0.45, 0.56]],
                        confidence=0.93,
                        is_active=True,
                    )
                    detections.append(det)
                    tracked_objects.append(track)
                else:
                    # In frame 15, motion was detected as hand withdrew cup
                    if t == 15:
                        scene_state["motion_detected"] = True

            elif event_class == "OBJECT_MOVED":
                # Object slides across table from left to right (x moves 0.2 -> 0.7)
                cx = 0.25 + (0.45 * (t / float(self.sequence_length)))
                cy = 0.55
                det = Detection(
                    detection_id=f"d_box_{t}",
                    class_id=39,
                    class_name="bottle",
                    confidence=0.91,
                    bbox_xyxy=[cx - 0.04, cy - 0.08, cx + 0.04, cy + 0.08],
                )
                vx = 0.45 / (self.sequence_length * self.time_delta_sec)
                track = TrackedObject(
                    track_id=4,
                    camera_id=camera_id,
                    class_name="bottle",
                    current_bbox=det.bbox_xyxy,
                    velocity_vector=[round(vx, 3), 0.0],
                    first_seen_timestamp=now,
                    last_seen_timestamp=frame_ts,
                    trajectory=[[round(cx, 3), round(cy, 3)]],
                    confidence=0.91,
                    is_active=True,
                )
                detections.append(det)
                tracked_objects.append(track)
                scene_state["motion_detected"] = True

            elif event_class == "PERSON_ENTERED":
                # Person appears in scene starting from frame 12
                if t >= 12:
                    p_x = 0.10 + 0.02 * (t - 12)
                    det = Detection(
                        detection_id=f"d_person_{t}",
                        class_id=0,
                        class_name="person",
                        confidence=0.95,
                        bbox_xyxy=[p_x, 0.20, p_x + 0.25, 0.85],
                    )
                    track = TrackedObject(
                        track_id=5,
                        camera_id=camera_id,
                        class_name="person",
                        current_bbox=det.bbox_xyxy,
                        velocity_vector=[0.05, 0.0],
                        first_seen_timestamp=now + timedelta(seconds=12 * self.time_delta_sec),
                        last_seen_timestamp=frame_ts,
                        trajectory=[[p_x + 0.12, 0.52]],
                        confidence=0.95,
                        is_active=True,
                    )
                    detections.append(det)
                    tracked_objects.append(track)
                    scene_state["motion_detected"] = True

            elif event_class == "PERSON_LEFT":
                # Person present in frames 0..18, then leaves scene
                if t <= 18:
                    p_x = 0.40 + 0.03 * t
                    det = Detection(
                        detection_id=f"d_person_{t}",
                        class_id=0,
                        class_name="person",
                        confidence=0.94,
                        bbox_xyxy=[p_x, 0.20, min(1.0, p_x + 0.25), 0.85],
                    )
                    track = TrackedObject(
                        track_id=6,
                        camera_id=camera_id,
                        class_name="person",
                        current_bbox=det.bbox_xyxy,
                        velocity_vector=[0.08, 0.0],
                        first_seen_timestamp=now,
                        last_seen_timestamp=frame_ts,
                        trajectory=[[p_x + 0.12, 0.52]],
                        confidence=0.94,
                        is_active=True,
                    )
                    detections.append(det)
                    tracked_objects.append(track)
                    scene_state["motion_detected"] = True

            elif event_class == "ZONE_LOITERING":
                # Person remains in the same zone continuously for all 30 frames with minimal jitter
                jitter_x = self.rng.uniform(-0.01, 0.01)
                jitter_y = self.rng.uniform(-0.01, 0.01)
                det = Detection(
                    detection_id=f"d_loiter_{t}",
                    class_id=0,
                    class_name="person",
                    confidence=0.96,
                    bbox_xyxy=[0.35 + jitter_x, 0.25 + jitter_y, 0.60 + jitter_x, 0.88 + jitter_y],
                )
                track = TrackedObject(
                    track_id=7,
                    camera_id=camera_id,
                    class_name="person",
                    current_bbox=det.bbox_xyxy,
                    velocity_vector=[0.002, 0.001],
                    first_seen_timestamp=now,
                    last_seen_timestamp=frame_ts,
                    trajectory=[[0.47, 0.56]],
                    confidence=0.96,
                    is_active=True,
                )
                detections.append(det)
                tracked_objects.append(track)

            elif event_class == "CAMERA_BLOCKED":
                # Camera gets obstructed starting at frame 10 (zero detections, extreme scene change)
                if t < 10:
                    det = Detection(
                        detection_id=f"d_p_{t}",
                        class_id=0,
                        class_name="person",
                        confidence=0.88,
                        bbox_xyxy=[0.30, 0.30, 0.55, 0.80],
                    )
                    detections.append(det)
                else:
                    scene_state["camera_blocked"] = True
                    scene_state["motion_detected"] = False

            elif event_class == "TASK_COMPLETED":
                # Person places object down and withdraws hand
                # Frames 0..15: Person with object moving; Frames 16..29: Object stays, person disappears
                det_obj = Detection(
                    detection_id=f"d_mug_{t}",
                    class_id=41,
                    class_name="cup",
                    confidence=0.92,
                    bbox_xyxy=[0.45, 0.60, 0.52, 0.72],
                )
                track_obj = TrackedObject(
                    track_id=8,
                    camera_id=camera_id,
                    class_name="cup",
                    current_bbox=det_obj.bbox_xyxy,
                    velocity_vector=[0.0, 0.0],
                    first_seen_timestamp=now,
                    last_seen_timestamp=frame_ts,
                    trajectory=[[0.48, 0.66]],
                    confidence=0.92,
                    is_active=True,
                )
                detections.append(det_obj)
                tracked_objects.append(track_obj)

                if t < 16:
                    det_pers = Detection(
                        detection_id=f"d_p_{t}",
                        class_id=0,
                        class_name="person",
                        confidence=0.91,
                        bbox_xyxy=[0.30, 0.20, 0.65, 0.80],
                    )
                    detections.append(det_pers)

            obs = Observation(
                observation_id=f"obs_syn_{session_id}_{t}",
                camera_id=camera_id,
                timestamp=frame_ts,
                frame_index=t,
                detections=detections,
                tracked_objects=tracked_objects,
                scene_state=scene_state,
            )
            observations.append(obs)

        annotation = TemporalAnnotation(
            sample_id=sample_id,
            label=event_class,
            label_id=CLASS_TO_ID[event_class],
            start_frame=0,
            end_frame=self.sequence_length - 1,
            event_start_frame=10,
            event_end_frame=25,
            confidence=1.0,
            annotator="synthetic_generator",
            notes=f"Synthetic sequence generated for {event_class}",
        )

        return SequenceSample(
            sample_id=sample_id,
            session_id=session_id,
            camera_id=camera_id,
            source_type="synthetic",
            sequence_length=self.sequence_length,
            fps=self.fps,
            start_timestamp=observations[0].timestamp,
            end_timestamp=observations[-1].timestamp,
            observations=observations,
            annotation=annotation,
            metadata={"generator": "SyntheticSequenceGenerator", "event_class": event_class},
        )

    def generate_dataset(
        self,
        samples_per_class: int = 20,
        num_sessions: int = 10,
    ) -> List[SequenceSample]:
        """Generates a balanced dataset partitioned across distinct recording sessions."""
        samples: List[SequenceSample] = []
        sessions = [f"session_{i:03d}" for i in range(num_sessions)]

        for cls_name in DEFAULT_EVENT_CLASSES:
            for s_idx in range(samples_per_class):
                session = sessions[s_idx % num_sessions]
                sample = self.generate_sample(cls_name, session)
                samples.append(sample)

        self.rng.shuffle(samples)
        return samples

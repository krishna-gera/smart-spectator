"""
Smart Spectator - Event Engine: Rolling Media Buffer & Event Clip Recording
Maintains bounded in-memory frame ring buffers per camera and generates MP4 event clips.
Conforms to Sections 24, 25, 26, 27, 63, 64 of Phase 4 specification.
"""

from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time
from typing import Dict, List, Optional, Tuple, Any
import uuid

import cv2
import numpy as np
import psutil

from shared.schemas.v1.models import Event, Recording
from services.hub_backend.config import settings
from services.hub_backend.database.connection import db_session


class BufferedFrame:
    """Represents a single frame cached in the rolling ring buffer."""

    def __init__(self, frame: np.ndarray, timestamp: float, frame_index: int):
        self.frame = frame
        self.timestamp = timestamp
        self.frame_index = frame_index


class CameraRollingBuffer:
    """
    Per-camera bounded rolling ring buffer.
    Continuously retains recent video frames and automatically discards old frames.
    Guarantees fixed maximum memory consumption.
    """

    def __init__(self, max_seconds: float = 30.0, max_frames: int = 300):
        self.max_seconds = max_seconds
        self.max_frames = max_frames
        self._buffer: deque[BufferedFrame] = deque(maxlen=max_frames)
        self._lock = threading.Lock()

    def add_frame(self, frame: np.ndarray, timestamp: Optional[float] = None, frame_index: int = 0) -> None:
        ts = timestamp if timestamp is not None else time.time()
        # Ensure we don't hold a massive reference if incoming frame is a large view
        buf_item = BufferedFrame(frame.copy(), ts, frame_index)
        with self._lock:
            self._buffer.append(buf_item)
            # Evict frames older than max_seconds
            cutoff = ts - self.max_seconds
            while self._buffer and self._buffer[0].timestamp < cutoff:
                self._buffer.popleft()

    def get_frames(self, start_ts: float, end_ts: float) -> List[BufferedFrame]:
        """Extracts all buffered frames between start_ts and end_ts."""
        with self._lock:
            return [f for f in self._buffer if start_ts <= f.timestamp <= end_ts]

    def get_all_frames(self) -> List[BufferedFrame]:
        with self._lock:
            return list(self._buffer)

    def frame_count(self) -> int:
        with self._lock:
            return len(self._buffer)


class ActiveRecordingSession:
    """Tracks frames being collected for an ongoing event recording."""

    def __init__(
        self,
        event_id: str,
        camera_id: str,
        pre_roll_start: float,
        event_start: float,
        post_roll_seconds: float = 5.0,
    ):
        self.event_id = event_id
        self.camera_id = camera_id
        self.pre_roll_start = pre_roll_start
        self.event_start = event_start
        self.post_roll_seconds = post_roll_seconds
        self.resolved_time: Optional[float] = None
        self.frames: List[BufferedFrame] = []
        self.is_finalized = False


class RecordingManager:
    """
    Orchestrates per-camera rolling buffers, event-triggered clip generation,
    storage quota management, and secure media file resolution.
    """

    def __init__(
        self,
        recordings_dir: Optional[Path] = None,
        snapshots_dir: Optional[Path] = None,
        pre_roll_seconds: float = 10.0,
        post_roll_seconds: float = 5.0,
        max_storage_gb: float = 10.0,
        retention_days: int = 14,
    ):
        self.recordings_dir = recordings_dir or settings.RECORDINGS_DIR
        self.snapshots_dir = snapshots_dir or settings.SNAPSHOTS_DIR
        self.pre_roll_seconds = pre_roll_seconds
        self.post_roll_seconds = post_roll_seconds
        self.max_storage_gb = max_storage_gb
        self.retention_days = retention_days

        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

        # Per-camera rolling ring buffers
        self._camera_buffers: Dict[str, CameraRollingBuffer] = {}
        # Active recording sessions: event_id -> ActiveRecordingSession
        self._active_recordings: Dict[str, ActiveRecordingSession] = {}
        self._lock = threading.Lock()

    def get_or_create_buffer(self, camera_id: str) -> CameraRollingBuffer:
        with self._lock:
            if camera_id not in self._camera_buffers:
                self._camera_buffers[camera_id] = CameraRollingBuffer(
                    max_seconds=self.pre_roll_seconds + 30.0, max_frames=300
                )
            return self._camera_buffers[camera_id]

    def ingest_frame(
        self, camera_id: str, frame: np.ndarray, timestamp: Optional[float] = None, frame_index: int = 0
    ) -> None:
        """Called whenever a decoded frame arrives from the stream engine."""
        buf = self.get_or_create_buffer(camera_id)
        ts = timestamp if timestamp is not None else time.time()
        buf.add_frame(frame, ts, frame_index)

        # Feed into any active recordings for this camera
        with self._lock:
            for session in list(self._active_recordings.values()):
                if session.camera_id == camera_id and not session.is_finalized:
                    session.frames.append(BufferedFrame(frame.copy(), ts, frame_index))

    def trigger_recording_start(self, event: Event) -> None:
        """Called when an event is confirmed to initiate clip capture."""
        now = time.time()
        camera_id = event.camera_id
        buf = self.get_or_create_buffer(camera_id)

        pre_roll_start = now - self.pre_roll_seconds
        pre_frames = buf.get_frames(pre_roll_start, now)

        with self._lock:
            session = ActiveRecordingSession(
                event_id=event.event_id,
                camera_id=camera_id,
                pre_roll_start=pre_roll_start,
                event_start=now,
                post_roll_seconds=self.post_roll_seconds,
            )
            session.frames.extend(pre_frames)
            self._active_recordings[event.event_id] = session

    def trigger_recording_resolve(self, event_id: str) -> None:
        """Called when an event is resolved to start post-roll timer before finalizing."""
        with self._lock:
            session = self._active_recordings.get(event_id)
            if session:
                session.resolved_time = time.time()

    def finalize_recording(self, event: Event) -> Optional[Recording]:
        """
        Encodes buffered frames into an MP4 clip and persists metadata.
        Runs asynchronously/background without blocking AI or streaming.
        """
        with self._lock:
            session = self._active_recordings.pop(event.event_id, None)

        if not session or not session.frames:
            # Fallback: pull whatever is in the rolling buffer
            buf = self.get_or_create_buffer(event.camera_id)
            frames = buf.get_all_frames()
        else:
            frames = session.frames

        if not frames:
            return None

        recording_id = f"rec_{uuid.uuid4().hex[:12]}"
        mp4_filename = f"event_{event.event_id}.mp4"
        mp4_path = self.recordings_dir / mp4_filename
        thumb_filename = f"snapshot_{event.event_id}.jpg"
        thumb_path = self.snapshots_dir / thumb_filename

        try:
            # Sort frames strictly by timestamp
            frames.sort(key=lambda f: f.timestamp)
            h, w = frames[0].frame.shape[:2]

            # Calculate FPS from frame timestamps
            duration = max(0.5, frames[-1].timestamp - frames[0].timestamp)
            calc_fps = max(1.0, min(30.0, len(frames) / duration))

            # Check disk free space to prevent disk-full system lockup (Section 21)
            try:
                free_mb = psutil.disk_usage(str(self.recordings_dir)).free / (1024 * 1024)
                if free_mb < settings.MIN_FREE_DISK_MB:
                    print(f"[RecordingManager] Low disk space ({free_mb:.1f} MB < {settings.MIN_FREE_DISK_MB} MB). Skipping clip write to preserve system stability.")
                    event.metadata["recording_degraded"] = True
                    event.metadata["recording_skipped_reason"] = "disk_full_threshold"
                    with db_session() as conn:
                        conn.execute(
                            "UPDATE events SET metadata_json = ? WHERE event_id = ?",
                            (json.dumps(event.metadata), event.event_id),
                        )
                    return None
            except Exception as e:
                print(f"[RecordingManager] Disk space check note: {e}")

            # Encode MP4 clip using OpenCV
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(mp4_path), fourcc, calc_fps, (w, h))
            for f in frames:
                writer.write(f.frame)
            writer.release()

            # Save snapshot thumbnail from middle frame
            mid_idx = len(frames) // 2
            mid_frame = frames[mid_idx].frame
            cv2.imwrite(str(thumb_path), mid_frame)

            file_size = mp4_path.stat().st_size if mp4_path.exists() else 0

            rec = Recording(
                recording_id=recording_id,
                camera_id=event.camera_id,
                event_id=event.event_id,
                file_path=str(mp4_path),
                thumbnail_path=str(thumb_path),
                start_time=datetime.fromtimestamp(frames[0].timestamp, tz=timezone.utc),
                end_time=datetime.fromtimestamp(frames[-1].timestamp, tz=timezone.utc),
                duration_seconds=round(duration, 2),
                file_size_bytes=file_size,
                codec="h264/mp4v",
                width=w,
                height=h,
                fps=round(calc_fps, 1),
                metadata={"total_frames": len(frames)},
            )

            # Persist to SQLite
            with db_session() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO cameras (camera_id, name, source_type, status)
                    VALUES (?, ?, 'phone', 'streaming')
                    """,
                    (rec.camera_id, f"Camera {rec.camera_id}"),
                )
                conn.execute(
                    """
                    INSERT INTO recordings (
                        recording_id, camera_id, file_path, thumbnail_path,
                        start_time, end_time, duration_seconds, file_size_bytes,
                        codec, width, height, fps, metadata_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rec.recording_id,
                        rec.camera_id,
                        rec.file_path,
                        rec.thumbnail_path,
                        rec.start_time.isoformat(),
                        rec.end_time.isoformat(),
                        rec.duration_seconds,
                        rec.file_size_bytes,
                        rec.codec,
                        rec.width,
                        rec.height,
                        rec.fps,
                        json.dumps(rec.metadata),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                # Link recording_id in events table
                conn.execute(
                    "UPDATE events SET recording_id = ? WHERE event_id = ?",
                    (rec.recording_id, event.event_id),
                )

            # Trigger retention cleanup in background
            threading.Thread(target=self.cleanup_storage, daemon=True).start()

            return rec

        except Exception as e:
            print(f"[RecordingManager] Error finalizing recording for '{event.event_id}': {e}")
            return None

    def resolve_safe_recording_path(self, recording_id: str) -> Optional[Path]:
        """
        Security validation (Sections 63, 64):
        Resolves recording_id via SQLite database and verifies file remains
        strictly within the authorized recordings directory. Prevents path traversal.
        """
        with db_session() as conn:
            cursor = conn.execute(
                "SELECT file_path FROM recordings WHERE recording_id = ?", (recording_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

        raw_path = Path(row["file_path"]).resolve()
        canonical_base = self.recordings_dir.resolve()

        # Path traversal guard: must be subpath of canonical recordings directory
        try:
            raw_path.relative_to(canonical_base)
        except ValueError:
            print(f"[RecordingSecurity] Blocked path traversal attempt: {raw_path}")
            return None

        if not raw_path.exists():
            return None

        return raw_path

    def cleanup_storage(self) -> None:
        """
        Deletes oldest recordings if total size exceeds max_storage_gb
        or recordings exceed retention_days. Never deletes active recordings.
        """
        try:
            now_ts = time.time()
            cutoff_ts = now_ts - (self.retention_days * 86400)
            max_bytes = int(self.max_storage_gb * 1024 * 1024 * 1024)

            with self._lock:
                active_event_ids = set(self._active_recordings.keys())

            with db_session() as conn:
                cursor = conn.execute(
                    "SELECT recording_id, file_path, thumbnail_path, file_size_bytes, created_at "
                    "FROM recordings ORDER BY created_at ASC"
                )
                records = cursor.fetchall()

            total_bytes = sum(r["file_size_bytes"] for r in records)
            deleted_ids = []

            for r in records:
                # Check retention days or storage quota
                is_expired = False
                try:
                    rec_time = datetime.fromisoformat(r["created_at"]).timestamp()
                    if rec_time < cutoff_ts:
                        is_expired = True
                except Exception:
                    pass

                needs_cleanup = is_expired or (total_bytes > max_bytes)

                if needs_cleanup:
                    rec_id = r["recording_id"]
                    # Never delete recording associated with currently active event
                    if any(ev_id in r["file_path"] for ev_id in active_event_ids):
                        continue

                    # Safely remove files
                    mp4_p = Path(r["file_path"])
                    if mp4_p.exists():
                        try:
                            mp4_p.unlink()
                        except Exception:
                            pass
                    if r.get("thumbnail_path"):
                        th_p = Path(r["thumbnail_path"])
                        if th_p.exists():
                            try:
                                th_p.unlink()
                            except Exception:
                                pass

                    total_bytes -= r["file_size_bytes"]
                    deleted_ids.append(rec_id)

            if deleted_ids:
                with db_session() as conn:
                    conn.executemany(
                        "DELETE FROM recordings WHERE recording_id = ?",
                        [(rid,) for rid in deleted_ids],
                    )
                print(f"[RecordingManager] Cleaned up {len(deleted_ids)} expired recordings.")

        except Exception as e:
            print(f"[RecordingManager] Cleanup storage error: {e}")

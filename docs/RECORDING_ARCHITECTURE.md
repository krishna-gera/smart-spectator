# Recording Architecture & Circular Buffer
## Bounded In-Memory Buffering & Local MP4 Generation

---

### 1. Requirements & Design Goals

1. **Zero-Latency Event Clipping:** When an incident occurs, the system must produce an MP4 clip that includes footage from *before* the event was detected (pre-roll) as well as *during* the event (post-roll).
2. **Bounded Memory Footprint:** Memory usage must remain strictly bounded regardless of camera uptime or framerate.
3. **Local Storage Integrity:** Files must be stored safely with path traversal protection and automated disk quota cleanup.

---

### 2. Rolling Circular Frame Buffer (`CameraRollingBuffer`)

- Implemented using Python's high-performance `collections.deque` with `maxlen=max_frames`.
- Frame ingestion:
  ```python
  class CameraRollingBuffer:
      def __init__(self, max_seconds: float = 3.0, max_frames: int = 150):
          self.max_seconds = max_seconds
          self.max_frames = max_frames
          self._buffer = deque(maxlen=max_frames)
  ```
- **Dual Eviction Strategy:**
  1. **Capacity Eviction:** If the buffer reaches `max_frames`, oldest frames are automatically discarded in $O(1)$ time.
  2. **Temporal Eviction:** On ingestion of frame $t_{now}$, frames with $t < (t_{now} - \text{max\_seconds})$ are pruned.
- Pre-roll retrieval returns a contiguous timestamp-ordered slice.

---

### 3. MP4 Encoding & Snapshot Generation

When `RecordingManager.finalize_recording(event)` is invoked:
1. Pre-roll frames and active event frames are assembled into a chronological sequence.
2. OpenCV `cv2.VideoWriter` encodes the sequence using standard `mp4v` / `avc1` codec.
3. The keyframe frame (at the moment of peak confidence) is extracted and saved as a JPEG snapshot thumbnail (`cv2.imwrite`).
4. File paths and clip metadata (duration, resolution, fps, bytes) are committed to SQLite.
5. The clip is linked to the event via `event.recording_id`.

---

### 4. Storage Quota & Path Traversal Security

- **Quota Management:** `enforce_storage_quota(max_bytes)` calculates directory size. If exceeded, oldest recordings are deleted in FIFO order, cleaning both the filesystem and the database.
- **Path Traversal Protection:**
  ```python
  def resolve_safe_recording_path(self, recording_id: str) -> Optional[Path]:
      # Fetches path from DB, checks Path(file_path).resolve()
      # Enforces that resolved path starts with resolved RECORDINGS_DIR.
  ```
  Prevents directory traversal attacks (`/recordings/../../etc/passwd`).

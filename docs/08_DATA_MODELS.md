# Smart Spectator — Database Schema & Data Models

**Document ID:** `SS-DOC-008`  
**Phase:** Phase 0 (Architecture & Foundation)  
**Status:** Approved  
**Storage Engine:** SQLite 3 (WAL Mode)  

---

## 1. Storage Architecture & Concurrency Model

Smart Spectator leverages an embedded **SQLite 3** database running in **WAL (Write-Ahead Logging)** mode with `NORMAL` synchronous settings. This enables non-blocking concurrent reads by client query threads and background AI engines while dedicated writer threads persist events and telemetry without lock contention.

Key SQLite Configuration Pragmas:
```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456; -- 256MB memory-mapped I/O
```

---

## 2. Entity-Relationship Diagram

```
+----------------+          +----------------+          +--------------------+
|    devices     | 1      N |    cameras     | 1      N |  monitoring_tasks  |
+----------------+<---------+----------------+<---------+--------------------+
| id (PK)        |          | id (PK)        |          | id (PK)            |
| device_name    |          | device_id (FK) |          | camera_id (FK)     |
| auth_token_hash|          | source_type    |          | target_class       |
| status         |          | stream_url     |          | expected_state     |
+----------------+          +-------+--------+          | roi_polygon        |
                                    |                   +---------+----------+
                                    | 1                           | 1
                                    |                             |
                                    | N                           | N
                            +-------v--------+          +---------v----------+
                            |    streams     |          |       events       |
                            +----------------+          +--------------------+
                            | id (PK)        |          | id (PK)            |
                            | camera_id (FK) |          | camera_id (FK)     |
                            | status         |          | task_id (FK)       |
                            | fps, bitrate   |          | event_type         |
                            +----------------+          | severity           |
                                                        | recording_id (FK)  |
                                                        +---------+----------+
                                                                  | 1
                                                                  |
                                                                  | 1
                                                        +---------v----------+
                                                        |    recordings      |
                                                        +--------------------+
                                                        | id (PK)            |
                                                        | camera_id (FK)     |
                                                        | file_path          |
                                                        | duration_seconds   |
                                                        | file_size_bytes    |
                                                        +--------------------+
```

---

## 3. SQL Table Definitions & Constraints

### 3.1 `devices` Table
Stores authenticated and paired physical hardware nodes.

```sql
CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    device_name TEXT NOT NULL,
    device_type TEXT NOT NULL DEFAULT 'android_phone',
    device_model TEXT,
    ip_address TEXT,
    mac_address TEXT,
    auth_token_hash TEXT,
    status TEXT NOT NULL CHECK(status IN ('discovered', 'pairing', 'paired', 'connected', 'disconnected', 'revoked')),
    battery_level REAL,
    is_charging INTEGER DEFAULT 0,
    battery_temperature_c REAL,
    app_version TEXT,
    last_seen DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
```

### 3.2 `cameras` Table
Abstract camera entities associated with devices or independent network sources.

```sql
CREATE TABLE IF NOT EXISTS cameras (
    camera_id TEXT PRIMARY KEY,
    device_id TEXT,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK(source_type IN ('phone', 'rtsp', 'onvif', 'ip', 'usb')),
    stream_url TEXT,
    width INTEGER NOT NULL DEFAULT 1280,
    height INTEGER NOT NULL DEFAULT 720,
    target_fps INTEGER NOT NULL DEFAULT 30,
    is_active INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'idle',
    lens_facing TEXT DEFAULT 'back',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(device_id) REFERENCES devices(device_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_cameras_device ON cameras(device_id);
```

### 3.3 `streams` Table
Operational sessions and streaming telemetry.

```sql
CREATE TABLE IF NOT EXISTS streams (
    stream_id TEXT PRIMARY KEY,
    camera_id TEXT NOT NULL,
    session_start DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    session_end DATETIME,
    current_fps REAL DEFAULT 0.0,
    current_bitrate_kbps REAL DEFAULT 0.0,
    dropped_frames_total INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'idle',
    FOREIGN KEY(camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_streams_camera ON streams(camera_id);
```

### 3.4 `monitoring_tasks` Table
User-configured visual intelligence rules and ROI boundaries.

```sql
CREATE TABLE IF NOT EXISTS monitoring_tasks (
    task_id TEXT PRIMARY KEY,
    camera_id TEXT NOT NULL,
    name TEXT NOT NULL,
    target_class TEXT NOT NULL,
    expected_state TEXT NOT NULL,
    trigger_condition TEXT NOT NULL,
    event_type TEXT NOT NULL,
    roi_polygon TEXT, -- JSON Array of normalized coordinates [[x,y], ...]
    notification_policy TEXT, -- JSON Object { "sound": true, "banner": true }
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tasks_camera ON monitoring_tasks(camera_id);
CREATE INDEX IF NOT EXISTS idx_tasks_active ON monitoring_tasks(is_active);
```

### 3.5 `recordings` Table
Metadata for video clips persisted from the circular ring buffer upon event trigger.

```sql
CREATE TABLE IF NOT EXISTS recordings (
    recording_id TEXT PRIMARY KEY,
    camera_id TEXT NOT NULL,
    file_path TEXT NOT NULL UNIQUE,
    thumbnail_path TEXT,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    duration_seconds REAL NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    codec TEXT NOT NULL DEFAULT 'h264',
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    fps REAL NOT NULL,
    metadata_json TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_recordings_camera ON recordings(camera_id);
CREATE INDEX IF NOT EXISTS idx_recordings_time ON recordings(start_time DESC);
```

### 3.6 `events` Table
Spatial-temporal security and task events emitted by the Event Engine.

```sql
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    camera_id TEXT NOT NULL,
    task_id TEXT,
    recording_id TEXT,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('info', 'low', 'medium', 'high', 'critical')),
    confidence REAL NOT NULL,
    summary TEXT NOT NULL,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    involved_track_ids TEXT, -- JSON Array of track IDs [1, 4]
    metadata_json TEXT, -- Serialized scene state and detection details
    FOREIGN KEY(camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE,
    FOREIGN KEY(task_id) REFERENCES monitoring_tasks(task_id) ON DELETE SET NULL,
    FOREIGN KEY(recording_id) REFERENCES recordings(recording_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_events_camera_time ON events(camera_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
```

### 3.7 `model_metadata` Table
Catalog of installed AI models, checkpoints, and Snapdragon NPU compilation records.

```sql
CREATE TABLE IF NOT EXISTS model_metadata (
    model_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    task_type TEXT NOT NULL,
    format TEXT NOT NULL,
    input_resolution TEXT NOT NULL, -- e.g. "[1, 3, 640, 640]"
    mean_inference_latency_ms REAL,
    current_backend TEXT NOT NULL,
    supports_npu INTEGER NOT NULL DEFAULT 0,
    weights_path TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### 3.8 `system_settings` Table
Key-value store for system configuration and threshold parameters.

```sql
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

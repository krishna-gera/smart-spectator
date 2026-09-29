"""
Smart Spectator - SQLite Database Schema Definition
Strictly conforms to docs/08_DATA_MODELS.md
"""

CREATE_TABLES_SQL = """
-- Pragmas for high performance concurrent local operations
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

-- 1. Devices Table
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

-- 2. Cameras Table
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

-- 3. Streams Table
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

-- 4. Monitoring Tasks Table
CREATE TABLE IF NOT EXISTS monitoring_tasks (
    task_id TEXT PRIMARY KEY,
    camera_id TEXT NOT NULL,
    name TEXT NOT NULL,
    target_class TEXT NOT NULL,
    expected_state TEXT NOT NULL,
    trigger_condition TEXT NOT NULL,
    event_type TEXT NOT NULL,
    roi_polygon TEXT,
    notification_policy TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tasks_camera ON monitoring_tasks(camera_id);

-- 5. Recordings Table
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

-- 6. Events Table
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
    involved_track_ids TEXT,
    metadata_json TEXT,
    FOREIGN KEY(camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE,
    FOREIGN KEY(task_id) REFERENCES monitoring_tasks(task_id) ON DELETE SET NULL,
    FOREIGN KEY(recording_id) REFERENCES recordings(recording_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_events_camera_time ON events(camera_id, timestamp DESC);

-- 7. Model Metadata Table
CREATE TABLE IF NOT EXISTS model_metadata (
    model_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    task_type TEXT NOT NULL,
    format TEXT NOT NULL,
    input_resolution TEXT NOT NULL,
    mean_inference_latency_ms REAL,
    current_backend TEXT NOT NULL,
    supports_npu INTEGER NOT NULL DEFAULT 0,
    weights_path TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 8. System Settings Table
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 9. Active Pairing Requests (In-memory / Ephemeral table for PIN verification)
CREATE TABLE IF NOT EXISTS pairing_requests (
    device_id TEXT PRIMARY KEY,
    device_name TEXT NOT NULL,
    device_model TEXT,
    verification_pin TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    attempts_remaining INTEGER DEFAULT 3
);
"""

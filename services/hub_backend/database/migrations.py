"""
Smart Spectator - Versioned Database Migration Engine
Conforms to Sections 17 & 19 of Phase 6 Master Specification.
Applies safe, forward-only schema migrations without destroying existing data.
"""

from datetime import datetime, timezone
import sqlite3
from typing import List, Tuple, Callable


MIGRATIONS: List[Tuple[int, str, str]] = [
    (
        1,
        "v1_baseline_tables",
        """
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

        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            camera_id TEXT NOT NULL,
            task_id TEXT,
            recording_id TEXT,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'detected',
            severity TEXT NOT NULL CHECK(severity IN ('info', 'low', 'medium', 'high', 'critical')),
            confidence REAL NOT NULL,
            summary TEXT NOT NULL,
            timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            start_time DATETIME,
            end_time DATETIME,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            involved_track_ids TEXT,
            zone_id TEXT,
            rule_id TEXT,
            explanation TEXT,
            metadata_json TEXT,
            FOREIGN KEY(camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE,
            FOREIGN KEY(task_id) REFERENCES monitoring_tasks(task_id) ON DELETE SET NULL,
            FOREIGN KEY(recording_id) REFERENCES recordings(recording_id) ON DELETE SET NULL
        );
        """,
    ),
    (
        2,
        "v2_phase4_intelligence_tables",
        """
        CREATE TABLE IF NOT EXISTS event_predictions (
            prediction_id TEXT PRIMARY KEY,
            camera_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            confidence REAL NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            affected_tracks TEXT,
            class_probabilities_json TEXT,
            metadata_json TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS zones (
            zone_id TEXT PRIMARY KEY,
            camera_id TEXT NOT NULL,
            name TEXT NOT NULL,
            polygon_json TEXT NOT NULL,
            color TEXT NOT NULL DEFAULT '#38bdf8',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS event_rules (
            rule_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            condition_json TEXT NOT NULL,
            actions_json TEXT NOT NULL,
            severity_override TEXT,
            cooldown_seconds REAL NOT NULL DEFAULT 15.0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS event_actions (
            action_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'executed',
            executed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            details_json TEXT,
            FOREIGN KEY(event_id) REFERENCES events(event_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS alert_delivery_log (
            delivery_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            channel TEXT NOT NULL,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 1,
            error_message TEXT,
            delivered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(event_id) REFERENCES events(event_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id TEXT PRIMARY KEY,
            timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            resource TEXT NOT NULL,
            metadata_json TEXT
        );
        """,
    ),
    (
        3,
        "v3_indexes_and_performance_hardening",
        """
        CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
        CREATE INDEX IF NOT EXISTS idx_cameras_device ON cameras(device_id);
        CREATE INDEX IF NOT EXISTS idx_streams_camera ON streams(camera_id);
        CREATE INDEX IF NOT EXISTS idx_recordings_camera ON recordings(camera_id);
        CREATE INDEX IF NOT EXISTS idx_events_camera_time ON events(camera_id, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
        CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity);
        CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
        CREATE INDEX IF NOT EXISTS idx_predictions_cam_time ON event_predictions(camera_id, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_zones_camera ON zones(camera_id);
        CREATE INDEX IF NOT EXISTS idx_rules_enabled ON event_rules(enabled);
        CREATE INDEX IF NOT EXISTS idx_actions_event ON event_actions(event_id);
        CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(timestamp DESC);
        """,
    ),
    (
        4,
        "v4_phase9_productization",
        """
        -- Add priority and timeline_milestones_json to events
        ALTER TABLE events ADD COLUMN priority TEXT NOT NULL DEFAULT 'MEDIUM';
        ALTER TABLE events ADD COLUMN timeline_milestones_json TEXT;

        -- Add is_locked to recordings for retention policy lock
        ALTER TABLE recordings ADD COLUMN is_locked INTEGER NOT NULL DEFAULT 0;

        -- Create notification_configs table
        CREATE TABLE IF NOT EXISTS notification_configs (
            config_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL CHECK(category IN ('Critical', 'Important', 'Informational')),
            is_enabled INTEGER NOT NULL DEFAULT 1,
            cooldown_seconds REAL NOT NULL DEFAULT 15.0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        -- Create system_configs table for categorized configurations
        CREATE TABLE IF NOT EXISTS system_configs (
            category TEXT NOT NULL,
            key TEXT NOT NULL,
            value_json TEXT NOT NULL,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(category, key)
        );

        -- Additional search indexes
        CREATE INDEX IF NOT EXISTS idx_events_priority ON events(priority);
        CREATE INDEX IF NOT EXISTS idx_events_search ON events(camera_id, event_type, confidence, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_recordings_search ON recordings(camera_id, start_time DESC, duration_seconds, file_size_bytes);
        """,
    ),
    (
        5,
        "v5_phase10_advanced_intelligence",
        """
        -- 1. Incidents Table
        CREATE TABLE IF NOT EXISTS incidents (
            incident_id TEXT PRIMARY KEY,
            incident_type TEXT NOT NULL,
            title TEXT NOT NULL,
            severity TEXT NOT NULL CHECK(severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
            status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')),
            summary TEXT NOT NULL,
            camera_ids_json TEXT NOT NULL,
            zone_ids_json TEXT,
            source_event_ids_json TEXT NOT NULL,
            context_json TEXT,
            acknowledged_at DATETIME,
            acknowledged_by TEXT,
            resolved_at DATETIME,
            resolved_by TEXT,
            resolution_notes TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status, severity);
        CREATE INDEX IF NOT EXISTS idx_incidents_created ON incidents(created_at DESC);

        -- 2. Event Relationships Table
        CREATE TABLE IF NOT EXISTS event_relationships (
            relationship_id TEXT PRIMARY KEY,
            relationship_type TEXT NOT NULL,
            event_a_id TEXT NOT NULL,
            event_b_id TEXT NOT NULL,
            camera_id TEXT,
            zone_id TEXT,
            time_delta_seconds REAL NOT NULL,
            confidence REAL NOT NULL,
            details_json TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(event_a_id) REFERENCES events(event_id) ON DELETE CASCADE,
            FOREIGN KEY(event_b_id) REFERENCES events(event_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_relationships_events ON event_relationships(event_a_id, event_b_id);
        CREATE INDEX IF NOT EXISTS idx_relationships_type ON event_relationships(relationship_type);

        -- 3. Event Patterns Table
        CREATE TABLE IF NOT EXISTS event_patterns (
            pattern_id TEXT PRIMARY KEY,
            pattern_type TEXT NOT NULL,
            event_types_json TEXT NOT NULL,
            camera_id TEXT,
            zone_id TEXT,
            frequency INTEGER NOT NULL DEFAULT 1,
            time_window_seconds REAL NOT NULL,
            confidence REAL NOT NULL,
            first_seen DATETIME NOT NULL,
            last_seen DATETIME NOT NULL,
            metadata_json TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_patterns_camera ON event_patterns(camera_id, pattern_type);

        -- 4. Statistical Baselines Table
        CREATE TABLE IF NOT EXISTS statistical_baselines (
            baseline_id TEXT PRIMARY KEY,
            metric_name TEXT NOT NULL,
            camera_id TEXT,
            hour_of_day INTEGER,
            day_of_week INTEGER,
            sample_count INTEGER NOT NULL DEFAULT 0,
            mean_value REAL NOT NULL DEFAULT 0.0,
            std_dev REAL NOT NULL DEFAULT 0.0,
            median_value REAL NOT NULL DEFAULT 0.0,
            min_value REAL NOT NULL DEFAULT 0.0,
            max_value REAL NOT NULL DEFAULT 0.0,
            last_updated DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_baselines_metric ON statistical_baselines(metric_name, camera_id, hour_of_day, day_of_week);

        -- 5. Anomalies Table
        CREATE TABLE IF NOT EXISTS anomalies (
            anomaly_id TEXT PRIMARY KEY,
            anomaly_type TEXT NOT NULL,
            score REAL NOT NULL,
            explanation TEXT NOT NULL,
            camera_id TEXT,
            source_event_ids_json TEXT,
            metric_name TEXT,
            baseline_mean REAL,
            observed_value REAL,
            timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_anomalies_time ON anomalies(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_anomalies_type ON anomalies(anomaly_type);

        -- 6. Human Feedback Table
        CREATE TABLE IF NOT EXISTS human_feedback (
            feedback_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            feedback TEXT NOT NULL CHECK(feedback IN ('CORRECT', 'INCORRECT', 'NOT_SURE')),
            notes TEXT,
            model_version TEXT,
            operator_id TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(event_id) REFERENCES events(event_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_feedback_event ON human_feedback(event_id);

        -- 7. Model Drift Logs Table
        CREATE TABLE IF NOT EXISTS model_drift_logs (
            log_id TEXT PRIMARY KEY,
            model_id TEXT NOT NULL,
            window_start DATETIME NOT NULL,
            window_end DATETIME NOT NULL,
            mean_confidence REAL NOT NULL,
            sample_count INTEGER NOT NULL,
            drift_detected INTEGER NOT NULL DEFAULT 0,
            drift_score REAL NOT NULL DEFAULT 0.0,
            warning_message TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_drift_model ON model_drift_logs(model_id, created_at DESC);
        """,
    ),
]


def init_migration_table(conn: sqlite3.Connection) -> None:
    """Ensures migration metadata table exists."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at DATETIME NOT NULL
        );
        """
    )
    conn.commit()


def get_current_version(conn: sqlite3.Connection) -> int:
    """Returns the highest applied schema version, or 0 if uninitialized."""
    init_migration_table(conn)
    cursor = conn.execute("SELECT COALESCE(MAX(version), 0) AS current_ver FROM schema_migrations")
    row = cursor.fetchone()
    if not row:
        return 0
    if isinstance(row, dict):
        return row.get("current_ver", 0)
    return row[0]


def apply_migrations(conn: sqlite3.Connection) -> int:
    """
    Applies any pending migrations in sequential order.
    Returns the count of newly applied migrations.
    """
    current_ver = get_current_version(conn)
    applied_count = 0

    for version, name, sql_script in MIGRATIONS:
        if version > current_ver:
            # Execute migration in transaction
            try:
                statements = [s.strip() for s in sql_script.split(";") if s.strip()]
                for stmt in statements:
                    try:
                        conn.execute(stmt)
                    except sqlite3.OperationalError as op_err:
                        if "duplicate column name" in str(op_err).lower():
                            continue
                        raise
                now_str = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (version, name, now_str),
                )
                conn.commit()
                applied_count += 1
            except Exception as e:
                conn.rollback()
                raise RuntimeError(f"Migration {version} ('{name}') failed: {e}") from e

    return applied_count


class MigrationTracker:
    """Convenience class providing object-oriented migration tracking."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_current_version(self) -> int:
        return get_current_version(self.conn)

    def run_migrations(self) -> int:
        return apply_migrations(self.conn)


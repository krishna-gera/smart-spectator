# Configuration Management Reference — v1.2.0

## 1. Architecture
Smart Spectator configurations are categorized into modular domains stored securely in the local SQLite database (`system_configs` table).

All parameters provide safe operational defaults and can be audited, modified, exported, and imported via REST API endpoints (`/api/v1/system/config`).

## 2. Configuration Domains

### `system` Domain
- `hub_name` *(string, default: "Smart Spectator Hub")*: Display name of the local edge node.
- `log_level` *(string, default: "INFO")*: Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`).
- `telemetry_enabled` *(boolean, default: true)*: Local telemetry gathering for monitoring dashboard.

### `ai_pipeline` Domain
- `target_fps` *(integer, default: 5)*: Default target sampling frame rate per camera stream.
- `confidence_threshold` *(float, default: 0.50)*: Minimum confidence for YOLOv8 object detections.
- `temporal_confidence_threshold` *(float, default: 0.70)*: Minimum confidence for SpectatorNet temporal events.
- `enable_npu` *(boolean, default: true)*: Attempt QNN / NPU hardware acceleration if supported.

### `storage` Domain
- `retention_days` *(integer, default: 30)*: Number of days before unflagged events and clips expire.
- `max_storage_gb` *(integer, default: 50)*: Soft disk storage quota for media recordings.
- `enable_auto_retention` *(boolean, default: true)*: Execute daily retention pruning routines.
- `pre_roll_seconds` *(integer, default: 5)*: Ring buffer pre-roll duration for event video captures.
- `post_roll_seconds` *(integer, default: 10)*: Post-trigger recording duration for event video captures.

### `notifications` Domain
- `global_cooldown_seconds` *(integer, default: 5)*: Minimum gap between any alerts hub-wide.
- `camera_cooldown_seconds` *(integer, default: 15)*: Minimum gap between alerts for a specific camera.
- `event_type_cooldown_seconds` *(integer, default: 60)*: Minimum gap for duplicate alerts of the same event type.
- `desktop_notifications` *(boolean, default: true)*: Forward alerts to local browser notifications.

### `security` Domain
- `pairing_pin_ttl_seconds` *(integer, default: 120)*: Validity window for camera pairing PINs.
- `require_client_auth` *(boolean, default: false)*: Enforce operator authentication for monitoring client access.

## 3. Safe Export & Import Specification
When exporting configuration for operational backup (`GET /api/v1/system/config/export`):
- All credentials, secrets, tokens (`API_KEY`, `JWT_SECRET`, `PIN_HASH`) are stripped or redacted.
- Sensitive paths are sanitized.
- Exported JSON can be reviewed and safely re-imported (`POST /api/v1/system/config/import`) across hubs.

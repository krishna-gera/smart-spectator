# Smart Spectator Operations Guide

This guide describes routine operational procedures, health monitoring, backup management, and maintenance tasks for the Smart Spectator edge hub.

---

## 1. Daily Operations & System Health

### 1.1 Monitoring Health Endpoints
- **Liveness Check**:
  ```bash
  curl -s http://localhost:8000/health
  ```
  Returns `200 OK` with basic status and uptime:
  ```json
  {"status":"ok","version":"1.0.0","uptime_seconds":86400}
  ```
- **Detailed Subsystem Diagnostic Probe**:
  ```bash
  curl -s http://localhost:8000/health/detailed | jq .
  ```
  Reports health across 7 subsystems:
  - `database`: SQLite connection check.
  - `stream_engine`: Active streams and frame metrics.
  - `ai_engine`: Detector & SpectatorNet loading status and inference provider.
  - `event_engine`: Pipeline queue depth and rule state.
  - `recorder`: Disk space availability and degraded flags.
  - `websocket`: Connected monitoring clients.
  - `device_manager`: Registered cameras count.

---

## 2. Backup & Recovery Operations

### 2.1 Generating a Hot Backup
Backups can be taken live while the Hub is actively processing video streams:
```bash
curl -X POST http://localhost:8000/system/backup
```
Response:
```json
{
  "status": "success",
  "backup_filename": "smart_spectator_backup_20260929_120000.db",
  "manifest_filename": "smart_spectator_backup_20260929_120000.json",
  "backup_path": "backups/smart_spectator_backup_20260929_120000.db",
  "manifest": {
    "version": "1.0.0",
    "timestamp": "2026-09-29T12:00:00.000000",
    "schema_version": 3,
    "table_counts": {"devices": 2, "events": 142, "rules": 4, "zones": 3},
    "backup_size_bytes": 106496,
    "checksum_sha256": "4a71c89f..."
  }
}
```

### 2.2 Restoring from Backup
Restores automatically take a pre-restore safety snapshot before applying the target database:
```bash
curl -X POST http://localhost:8000/system/restore \
  -H "Content-Type: application/json" \
  -d '{"backup_filename": "smart_spectator_backup_20260929_120000.db"}'
```
If the backup file is corrupt or invalid, the restore aborts cleanly, and the database remains on the pre-restore snapshot.

---

## 3. Storage Retention & Pruning

Smart Spectator automatically monitors disk space before writing any event clip:
- If available storage falls below **500 MB** (`MIN_FREE_DISK_MB`), new video writes are bypassed, and events are flagged as `recording_degraded`.
- To purge old recordings manually:
  ```bash
  # Delete recordings older than 7 days
  find recordings/ -name "*.mp4" -mtime +7 -delete
  ```
- To prune snapshots older than 3 days:
  ```bash
  find snapshots/ -name "*.jpg" -mtime +3 -delete
  ```

---

## 4. Log Inspection & Rotation

Logs are placed in `logs/smart_spectator.log`. The logging framework uses `RotatingFileHandler`:
- Maximum file size: **5 MB**.
- Max backup files: **5**.
- Maximum log footprint on disk: **~30 MB**.

To view live application logs:
```bash
tail -f logs/smart_spectator.log
```
All tokens and PINs are automatically redacted.

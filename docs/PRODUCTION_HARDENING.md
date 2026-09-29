# Production Hardening Specification

This document details the hardening policies, fault tolerance mechanisms, and resource protections implemented in Smart Spectator for 24/7 edge execution.

---

## 1. Resilience & Fault Tolerance Matrix

| Failure Mode | Detection Mechanism | Immediate Action | Recovery Strategy |
| :--- | :--- | :--- | :--- |
| **Android Camera Network Drop** | Transport socket ping timeout / `onDone` callback | State transitions to `reconnecting`, stream paused | Exponential backoff (1s, 2s, 4s, 8s, 16s, max 30s) up to 10 attempts. Resets on handshake. |
| **Android App Minimized / Screen Off** | `WidgetsBindingObserver.didChangeAppLifecycleState` | Camera controller disposed, streaming paused | On `resumed`, reinitializes camera controller and reconnects transport. |
| **Host Disk Space Exhaustion (< 500MB)** | Pre-write check in `ClipRecorder.save_event_clip` via `shutil.disk_usage` | Skips MP4 encoding; logs warning; logs degrade flag | Marks event `recording_degraded: true` with reason `disk_full_threshold`. Retains telemetry without filling disk. |
| **Database Lock / Busy (SQLite)** | WAL mode + busy timeout in `get_db_connection` | Blocks up to 5000ms for writer to release lock | Uses WAL mode for concurrent readers + single writer. Auto-checkpoints periodically. |
| **Unpaired / Revoked Device Attempting Stream** | Validation in `streams.py` and active session tracker | Rejects handshake with HTTP 403 / WS 4001; active session killed | Camera device must be re-paired using 6-digit PIN before streaming can resume. |
| **Memory Buffer Overflow (Hub Stream)** | Ring buffer length check in `StreamIngestSession` | Drop oldest unconsumed frames | Preserves strict bounded memory (default 90 frames / ~3s buffer) even under high downstream load. |
| **AI Processing Latency Spike** | Async queue depth monitoring in `AIWorker` | Drops stale intermediate frames, processes latest | Ensures real-time latency doesn't accumulate queue lag. |

---

## 2. Security Boundaries & Input Sanitization

1. **Authentication Token Handling**:
   - WebSockets and HTTP routes accept tokens via `Authorization: Bearer <token>` or `X-Auth-Token` headers.
   - Query string token support is maintained for legacy WebSockets but logs redact sensitive tokens automatically.
2. **Log Sanitization**:
   - All log records pass through `SensitiveDataFilter`.
   - Regular expressions match bearer tokens, session IDs, and authentication PINs, replacing them with `[REDACTED]`.
3. **Path Traversal Guards**:
   - File serving endpoints for recordings and snapshots strictly resolve canonical paths and ensure they remain inside designated directories (`recordings/`, `snapshots/`, `backups/`).
4. **Input Constraints**:
   - Device IDs: Validated against standard UUID format (`^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`).
   - Pairing PINs: Enforced 6 numeric digits (`^\d{6}$`).
   - Rule names & Zone labels: Length-bounded strings (1–64 characters) stripped of control characters.

---

## 3. Storage & Database Management

- **SQLite WAL Mode**: Write-Ahead Logging (`PRAGMA journal_mode=WAL;`) ensures simultaneous reads while transactions write.
- **Foreign Keys**: `PRAGMA foreign_keys = ON;` is enforced on every connection pool checkout.
- **Hot Backups**:
  - `backup_database(db_path, backup_path)` uses `sqlite3.Connection.backup()` to create point-in-time snapshots while the application remains live.
  - Manifest generation records schema version, table counts, row statistics, and SHA-256 integrity hash.
- **Rollback Safety**:
  - Before applying any restore, the system automatically takes a pre-restore snapshot of the current state (`pre_restore_*.db`), allowing non-destructive recovery if a restore payload fails integrity validation.

# Smart Spectator Troubleshooting Guide

This guide provides diagnosis steps and remediation procedures for common operational issues encountered in Smart Spectator deployments.

---

## 1. Quick Diagnostic Checklist

When encountering an issue, run:
```bash
# 1. Check process liveness
curl -s http://localhost:8000/health

# 2. Check full diagnostic report
curl -s http://localhost:8000/health/detailed | jq .

# 3. Check logs for warnings/errors
grep -E "WARNING|ERROR|CRITICAL" logs/smart_spectator.log | tail -n 20

# 4. Check disk usage
df -h .
```

---

## 2. Common Scenarios & Resolutions

### 2.1 Camera Stream Shows Disconnected or Reconnecting Loop
- **Symptoms**: Monitoring client shows offline camera or Android camera screen shows "Reconnecting (attempt X/10)".
- **Causes**:
  1. Phone Wi-Fi switched or disconnected from Hub network.
  2. Camera device pairing was revoked from Hub UI.
  3. Hub IP address changed (DHCP lease renewed).
- **Remediation**:
  1. Ensure both host and phone are on the same Wi-Fi subnet.
  2. Verify device registration via `GET /devices`. If revoked, generate a new PIN in the Hub and re-pair the phone.
  3. Check IP address on Hub host (`ip a` or `ifconfig`) and verify phone connects to the right IP.

### 2.2 Video Recording Degraded / Clips Not Generating
- **Symptoms**: Events are detected and logged in the timeline, but video clip playback is unavailable or event has `recording_degraded: true`.
- **Causes**: Free disk space is lower than `500 MB` threshold (`MIN_FREE_DISK_MB`).
- **Remediation**:
  1. Check free space with `df -h`.
  2. Clean up old recordings: `rm -rf recordings/old_*.mp4`.
  3. Check `recorder` block in `GET /health/detailed` to confirm `disk_available_mb > 500`.

### 2.3 Low Frame Rate / High Inference Latency
- **Symptoms**: Inference takes > 30ms per frame or FPS drops below 20.
- **Causes**:
  1. Execution provider fell back to unoptimized CPU provider.
  2. Multiple heavy CPU-bound processes competing on edge device.
- **Remediation**:
  1. Inspect `GET /system/hardware` to verify available providers.
  2. Ensure ONNX Runtime execution provider (CoreML, DirectML, QNN, OpenVINO) is properly loaded.
  3. Use quantized INT8 model artifact (`spectatornet_v1_int8.onnx`).
  4. Ensure motion gating is enabled in detector configuration to skip redundant static frames.

### 2.4 Database Locked / Busy Errors
- **Symptoms**: Log messages containing `sqlite3.OperationalError: database is locked`.
- **Causes**: Long-running read queries or concurrent direct connections outside connection pool.
- **Remediation**:
  1. Verify WAL mode is active:
     ```bash
     sqlite3 smart_spectator.db "PRAGMA journal_mode;"
     ```
     Should return `wal`.
  2. Ensure all custom scripts use the context manager `get_db_connection()`, which configures a 5000ms busy timeout.

### 2.5 Android Camera Daemon Lockup
- **Symptoms**: Camera screen shows black preview or camera initialization error after phone was locked.
- **Causes**: Native Android Camera2 daemon not properly released during backgrounding.
- **Remediation**:
  - Smart Spectator includes a `WidgetsBindingObserver` in `camera_screen.dart` to release hardware automatically when backgrounded. If a crash occurred, restart the Android app or toggle airplane mode to reset the HAL.

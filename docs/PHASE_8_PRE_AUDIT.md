# Phase 8 Pre-Implementation Audit Report

## 1. Audit Metadata
- **Audit Timestamp**: 2026-09-29T16:48:30+05:30
- **Base Git Commit**: `fd55f6d` (`release: Smart Spectator 1.0.0`)
- **Current Version**: `1.0.0`
- **Working Tree State**: Clean (0 uncommitted changes)
- **Baseline Test Suite**: **85 tests passing**, 0 failures, 108 deprecation warnings, duration 9.25s.

---

## 2. Baseline System State

### 2.1 Versioning & Interfaces
- **Application Version**: `1.0.0` (in `services/hub_backend/config.py`)
- **API Version**: `v1` (Routes mounted under `/api/v1/...` and root `/...`)
- **Database Schema Version**: `3` (tracked via `schema_migrations`: `001_initial_schema`, `002_add_performance_indexes`, `003_add_device_telemetry`)
- **Protocol Version**: `1` (24-byte binary framing header: `0x53 0x53 0x01 ...`)

### 2.2 Model Artifacts & Manifest
- **Manifest**: `ai/models/releases/manifest.json`
- **Release Models**:
  - `spectatornet_v1.onnx`: FP32 ONNX model (`(1, 30, 166)` -> `(1, 5)`), SHA-256 `47228800f7e491c36087b32408018e69fa090b8f411aa6027a0808cf70ddcc0d`
  - `spectatornet_v1_int8.onnx`: INT8 dynamically quantized ONNX model (`(1, 30, 166)` -> `(1, 5)`), SHA-256 `c86eec085be9e7fec3bf310b8cf896791523ec3e33f3801ea8dc776100eb743c`
  - `detector_v1.onnx`: YOLOv8n detector (`(1, 3, 640, 640)`), SHA-256 `43916e788eb23528b746a583e78696ec09139268f76e3b2e7a177ff26e0eef2a`

### 2.3 Inference Providers Hierarchy
- **Target Primary**: `QNNExecutionProvider` (Qualcomm Snapdragon Hexagon NPU via Qualcomm AI Engine Direct)
- **Secondary**: `DirectMLExecutionProvider` (Windows on ARM / Adreno GPU) / `CoreMLExecutionProvider` (macOS Apple Silicon)
- **Fallback**: `CPUExecutionProvider` (AVX2 / NEON)
- **Current Host Providers**: `['CoreMLExecutionProvider', 'AzureExecutionProvider', 'CPUExecutionProvider']`. Physical Snapdragon hardware is pending on this host; fallback executed cleanly with zero crashes.

### 2.4 Existing Startup Commands
- Development: `./scripts/start_dev.sh`
- Production: `./scripts/start_production.sh`
- Benchmark: `python3 scripts/benchmark_hardware.py`
- Scenarios: `python3 scripts/demo_scenarios.py`

---

## 3. Discrepancies & Known Limitations Identified

1. **Hardware Detection Endpoint Path**:
   - Section 2 specifies `GET /api/v1/system/hardware`.
   - Current implementation provides `GET /system/hardware` and `GET /api/v1/system/telemetry`. We should ensure `GET /api/v1/system/hardware` and `GET /api/v1/system/diagnostics` (Section 21) are fully exposed and return exact structured runtime info.
2. **Windows PowerShell Scripts**:
   - Phase 7 provided Bash startup scripts (`start_dev.sh`, `start_production.sh`).
   - Windows PowerShell scripts (`install_windows.ps1`, `start_windows.ps1`, `stop_windows.ps1`, `health_windows.ps1`, `uninstall_windows.ps1`, `service_status.ps1`) are required for the target Snapdragon Windows PC.
3. **Model Integrity Startup Validation**:
   - Currently, checksum verification exists in benchmark/release scripts and unit tests. It must be integrated into hub startup and diagnostics (`GET /api/v1/system/diagnostics`) with `MODEL_INTEGRITY_ERROR` status if tampered.
4. **Android Build Verification**:
   - Need comprehensive documentation and validation for release APK/AAB build with signed config, CameraX, and MediaCodec H.264 transport.
5. **Offline & Multi-Camera Validation**:
   - Need explicit offline test (`tests/test_offline_mode.py`) asserting zero external requests.
   - Dedicated multi-camera isolation test (`tests/test_multi_camera_isolation.py`) verifying strict isolation of decoder, AI queue, tracker, events, and recordings between cameras.
6. **Diagnostics & Doctor Scripts**:
   - Create `scripts/doctor.py` and `scripts/validate_snapdragon_runtime.py` and `scripts/live_pipeline_diagnostics.py`.

---

## 4. Audit Verdict
All 85 baseline tests pass. The codebase is solid, modular, and ready for Phase 8 real-device deployment, validation, and demo hardening.

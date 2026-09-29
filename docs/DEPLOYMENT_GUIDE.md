# Smart Spectator Deployment Guide

This guide walks through deploying the Smart Spectator Hub on edge host machines (Linux, Snapdragon on Windows / WoA, macOS) and installing the Camera and Monitoring applications.

---

## 1. Prerequisites

### Edge Hub Host
- **Python**: 3.10+ (Recommended: Python 3.10 or 3.11)
- **C/C++ Build Tools**: For compiling ONNX Runtime dependencies if wheels are absent.
- **Hardware Acceleration (Optional but Recommended)**:
  - **Qualcomm Snapdragon**: Snapdragon X Elite / 8cx Gen 3 with Qualcomm Neural Processing SDK (QNN) or DirectML.
  - **Apple Silicon**: CoreML execution provider supported out-of-the-box.
  - **x86_64 / Generic ARM64**: OpenVINO or optimized CPU execution provider (OpenMP / AVX2 / NEON).
- **Disk Space**: 2 GB minimum free disk space for base models, database, and rolling recordings.
- **Network**: Local Area Network (Wi-Fi or Ethernet), port 8000 accessible to local camera phones and monitoring clients.

### Camera Device
- **Android**: Android 9.0 (API 28) or higher with camera permissions enabled.
- **Hardware**: Mid-range or modern Android phone connected to the same LAN as the Hub.

---

## 2. Edge Hub Setup

### 2.1 Repository Setup & Environment
```bash
git clone https://github.com/krishna-gera/smart-spectator.git
cd smart-spectator

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 2.2 Environment Configuration
Copy the production environment template:
```bash
export SMART_SPECTATOR_ENV=production
export HUB_HOST=0.0.0.0
export HUB_PORT=8000
export LOG_LEVEL=INFO
```
Alternatively, customize `.env` in the project root.

### 2.3 Initialize Database & Migrations
Migrations run automatically on hub launch. To run them manually or verify schema:
```bash
python3 -c "
from services.hub_backend.database.connection import get_db_connection
from services.hub_backend.database.migrations import MigrationTracker
with get_db_connection() as conn:
    tracker = MigrationTracker(conn)
    applied = tracker.run_migrations()
    print(f'Applied {applied} migrations. Schema version: {tracker.get_current_version()}')
"
```

### 2.4 Download or Validate Model Artifacts
Ensure release artifacts exist in `ai/models/releases/`:
```bash
python3 -c "
import json
with open('ai/models/releases/manifest.json') as f:
    manifest = json.load(f)
print('Verified release models:', list(manifest['models'].keys()))
"
```

---

## 3. Running the Hub

### Development Mode
```bash
./scripts/start_dev.sh
```

### Production Mode (Background / Systemd Service)
```bash
./scripts/start_production.sh
```

#### Systemd Unit File (`/etc/systemd/system/smart-spectator.service`)
```ini
[Unit]
Description=Smart Spectator Visual Intelligence Hub
After=network.target

[Service]
Type=simple
User=spectator
WorkingDirectory=/opt/smart-spectator
ExecStart=/opt/smart-spectator/venv/bin/python -m uvicorn services.hub_backend.main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=on-failure
RestartSec=5s
Environment=SMART_SPECTATOR_ENV=production
Environment=PYTHONPATH=/opt/smart-spectator

# Sandboxing
ProtectSystem=full
ProtectHome=read-only
ReadWritePaths=/opt/smart-spectator/recordings /opt/smart-spectator/snapshots /opt/smart-spectator/logs /opt/smart-spectator/backups /opt/smart-spectator/data

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable smart-spectator
sudo systemctl start smart-spectator
sudo systemctl status smart-spectator
```

---

## 4. Android Camera Application Deployment

1. Open `apps/camera` in Android Studio or terminal.
2. Ensure Flutter 3.19+ and Android SDK 34 are installed.
3. Build release APK:
   ```bash
   cd apps/camera
   flutter pub get
   flutter build apk --release
   ```
4. Install APK onto the Android phone:
   ```bash
   adb install -r build/app/outputs/flutter-apk/app-release.apk
   ```
5. Launch app, grant Camera permissions, and enter Hub IP (`http://<HUB_IP>:8000`) and the 6-digit PIN generated from the Hub UI.

---

## 5. Web Monitoring Client Access

Open any modern browser (Chrome, Firefox, Safari, Edge) on a device in the same local network:
```
http://<HUB_IP>:8000/
```
The responsive monitoring interface allows:
- Real-time video grid with sub-100ms latency.
- Event timeline, filterable by class, severity, and zone.
- Visual polygon zone editor.
- Rule creation and automated actions.
- System diagnostics, backup export, and hardware telemetry.

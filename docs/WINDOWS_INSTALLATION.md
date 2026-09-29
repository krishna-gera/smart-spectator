# Windows Production Deployment Guide (Snapdragon & x86_64)

This guide documents deploying the Smart Spectator Hub on Snapdragon-powered Windows PCs (such as Snapdragon X Elite, X Plus, and 8cx Gen 3 laptops) and standard Windows 10/11 machines.

---

## 1. System Requirements

### Snapdragon PC (Primary Target)
- **OS**: Windows 11 on ARM64 (Build 22621+)
- **Processor**: Qualcomm Snapdragon X Elite, Snapdragon X Plus, or Snapdragon 8cx Gen 3
- **Memory**: Minimum 16 GB unified RAM
- **Storage**: Minimum 5 GB free SSD space for recordings and model weights
- **Network**: Local Wi-Fi network (same subnet as Android camera phones)

### Prerequisites Installation
1. Install Python 3.10 or 3.11 for Windows on ARM from [python.org](https://www.python.org/downloads/windows/).
   *(Ensure "Add Python to PATH" is checked during setup).*
2. Ensure PowerShell 5.1+ or PowerShell 7+ is installed.

---

## 2. Automated Installation

Open PowerShell as Administrator (or standard user with execution policy enabled):
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Clone the repository and run the automated installer:
```powershell
git clone https://github.com/krishna-gera/smart-spectator.git
cd smart-spectator
.\scripts\install_windows.ps1
```

The installer performs the following checks:
1. Verifies Windows OS and identifies ARM64 architecture.
2. Creates an isolated virtual environment (`venv\`).
3. Installs pinned dependencies (`onnxruntime`, `fastapi`, `uvicorn`, `opencv-python`, etc.).
4. Initializes the SQLite database in WAL mode and runs forward schema migrations.
5. Verifies SHA-256 integrity of release models in `ai\models\releases\`.
6. Checks port availability for REST/WS (8000) and TCP media stream (8554).

---

## 3. Service & Process Management

### Starting the Hub
To start the Hub in background mode with automated PID tracking and log redirection:
```powershell
.\scripts\start_windows.ps1
```

To run in the foreground with live console logs:
```powershell
.\scripts\start_windows.ps1 -Foreground
```

### Checking Status
Run the subsystem health probe:
```powershell
.\scripts\service_status.ps1
```
Output:
```
Hub:      RUNNING
Database: HEALTHY
AI:       READY
Recorder: READY
```

### Stopping the Hub
To shut down the Hub cleanly:
```powershell
.\scripts\stop_windows.ps1
```
This signals the running uvicorn process, gracefully checkpoints SQLite WAL transactions, flushes active video clips, and terminates cleanly.

---

## 4. Hardware Acceleration (Qualcomm QNN / DirectML)

### On Qualcomm Snapdragon Systems:
When Qualcomm AI Engine Direct runtime is present, ONNX Runtime automatically uses `QNNExecutionProvider` (Hexagon NPU).
If direct QNN drivers are not yet installed, the system automatically falls back to `DmlExecutionProvider` (DirectML utilizing Adreno GPU) or multi-threaded CPU NEON.

Verify active provider via the diagnostics endpoint:
```powershell
.\scripts\health_windows.ps1
```
or in browser: `http://localhost:8000/api/v1/system/hardware`.

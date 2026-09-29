# Smart Spectator - Windows PowerShell Automated Installation Script
# Conforms to Section 4 of Phase 8 Master Specification.
# Installs dependencies, sets up virtualenv, validates hardware, and initializes database.

[CmdletBinding()]
param (
    [string]$PythonPath = "python",
    [switch]$SkipModelValidation
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Smart Spectator - Snapdragon Windows Hub Installer     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Verify Operating System
if (-not $IsWindows -and $env:OS -notmatch "Windows") {
    Write-Error "[FAIL] This installer must be executed on a Windows operating system."
}
Write-Host "[OK] Operating System: Windows detected ($([System.Environment]::OSVersion))" -ForegroundColor Green

# 2. Verify Architecture
$arch = $env:PROCESSOR_ARCHITECTURE
Write-Host "[INFO] Detected Architecture: $arch" -ForegroundColor Yellow
if ($arch -eq "ARM64") {
    Write-Host "[OK] Snapdragon Windows on ARM (WoA) architecture detected!" -ForegroundColor Green
} else {
    Write-Host "[WARN] Running on $arch (x86_64 emulation or native). CPU/DirectML will be prioritized." -ForegroundColor Yellow
}

# 3. Verify Python 3.10+
try {
    $pyVer = & $PythonPath -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
    Write-Host "[OK] Python Version: $pyVer" -ForegroundColor Green
    $major, $minor = $pyVer.Split(".")[0..1]
    if ([int]$major -lt 3 -or ([int]$major -eq 3 -and [int]$minor -lt 10)) {
        Write-Error "[FAIL] Python 3.10 or higher is required. Found Python $pyVer"
    }
} catch {
    Write-Error "[FAIL] Python not found or failed execution. Please ensure Python 3.10+ is in PATH."
}

# 4. Create Virtual Environment
$venvDir = Join-Path $PSScriptRoot "..\venv"
if (-not (Test-Path $venvDir)) {
    Write-Host "[INFO] Creating virtual environment at $venvDir..." -ForegroundColor Yellow
    & $PythonPath -m venv $venvDir
}
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvPip = Join-Path $venvDir "Scripts\pip.exe"

# 5. Upgrade pip and install dependencies
Write-Host "[INFO] Upgrading pip..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip

$reqFile = Join-Path $PSScriptRoot "..\requirements.txt"
if (Test-Path $reqFile) {
    Write-Host "[INFO] Installing dependencies from requirements.txt..." -ForegroundColor Yellow
    & $venvPip install -r $reqFile
} else {
    Write-Warning "[WARN] requirements.txt not found. Skipping pip install."
}

# 6. Create Required Directories
$dirs = @("recordings", "snapshots", "logs", "backups", "data", "artifacts\phase8")
foreach ($d in $dirs) {
    $target = Join-Path $PSScriptRoot "..\$d"
    if (-not (Test-Path $target)) {
        New-Item -ItemType Directory -Path $target -Force | Out-Null
    }
}
Write-Host "[OK] Storage directories initialized." -ForegroundColor Green

# 7. Initialize Database & Migrations
Write-Host "[INFO] Initializing SQLite database and migrations..." -ForegroundColor Yellow
& $venvPython -c "
from services.hub_backend.database.connection import init_database, get_db_connection
from services.hub_backend.database.migrations import MigrationTracker
init_database()
with get_db_connection() as conn:
    tracker = MigrationTracker(conn)
    applied = tracker.run_migrations()
    print(f'Database verified. Current schema version: {tracker.get_current_version()}')
"
Write-Host "[OK] Database schema initialized and verified." -ForegroundColor Green

# 8. Validate Model Checksums
if (-not $SkipModelValidation) {
    Write-Host "[INFO] Validating release model checksums..." -ForegroundColor Yellow
    & $venvPython -c "
from ai.models.validator import model_validator
report = model_validator.validate_all()
if report['status'] == 'READY':
    print('[OK] All release models match manifest SHA-256.')
else:
    print(f'[WARN] Model validation status: {report[\"status\"]}. Error: {report.get(\"error\")}')
"
}

# 9. Verify Ports
$port8000Used = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
$port8554Used = Get-NetTCPConnection -LocalPort 8554 -ErrorAction SilentlyContinue
if ($port8000Used) {
    Write-Warning "[WARN] Port 8000 is currently in use."
} else {
    Write-Host "[OK] Port 8000 (REST / WebSocket) is available." -ForegroundColor Green
}
if ($port8554Used) {
    Write-Warning "[WARN] Port 8554 (TCP Media Stream) is currently in use."
} else {
    Write-Host "[OK] Port 8554 (TCP Media Stream) is available." -ForegroundColor Green
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Installation Complete!                                 " -ForegroundColor Green
Write-Host "  To launch the Hub, run: .\scripts\start_windows.ps1    " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

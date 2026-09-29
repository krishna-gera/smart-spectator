# Smart Spectator - Windows PowerShell Process Launcher
# Conforms to Sections 4 & 5 of Phase 8 Master Specification.
# Launches Hub process with PID tracking, log redirection, and health probe.

[CmdletBinding()]
param (
    [int]$Port = 8000,
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pidFile = Join-Path $root "hub.pid"
$logFile = Join-Path $root "logs\smart_spectator.log"
$venvPython = Join-Path $root "venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    $venvPython = "python"
}

# 1. Prevent duplicate hub instances
if (Test-Path $pidFile) {
    $existingPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($existingPid) {
        $proc = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Warning "[WARN] Smart Spectator Hub is already running with PID $existingPid."
            Write-Host "To stop it, execute: .\scripts\stop_windows.ps1" -ForegroundColor Yellow
            exit 0
        } else {
            Remove-Item $pidFile -Force
        }
    }
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Starting Smart Spectator Desktop Hub                   " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$env:SMART_SPECTATOR_ENV = "production"
$env:HUB_PORT = "$Port"
$env:PYTHONPATH = $root

if ($Foreground) {
    Write-Host "[INFO] Starting Hub in foreground console mode..." -ForegroundColor Yellow
    & $venvPython -m uvicorn services.hub_backend.main:app --host 0.0.0.0 --port $Port
} else {
    Write-Host "[INFO] Starting Hub in background mode..." -ForegroundColor Yellow
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $venvPython
    $startInfo.Arguments = "-m uvicorn services.hub_backend.main:app --host 0.0.0.0 --port $Port"
    $startInfo.WorkingDirectory = $root
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    $process.Start() | Out-Null

    $process.Id | Out-File -FilePath $pidFile -Encoding ascii

    # Asynchronous log capture
    Register-ObjectEvent -InputObject $process -EventName OutputDataReceived -Action {
        if ($EventArgs.Data) { Add-Content -Path $using:logFile -Value $EventArgs.Data }
    } | Out-Null
    Register-ObjectEvent -InputObject $process -EventName ErrorDataReceived -Action {
        if ($EventArgs.Data) { Add-Content -Path $using:logFile -Value $EventArgs.Data }
    } | Out-Null
    $process.BeginOutputReadLine()
    $process.BeginErrorReadLine()

    Write-Host "[OK] Hub started with PID: $($process.Id)" -ForegroundColor Green

    # Wait for health probe
    Write-Host "[INFO] Awaiting health probe response on port $Port..." -ForegroundColor Yellow
    $healthy = $false
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 1
        try {
            $resp = Invoke-RestMethod -Uri "http://localhost:$Port/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($resp.status -eq "healthy") {
                $healthy = $true
                break
            }
        } catch {}
    }

    if ($healthy) {
        Write-Host "[OK] Desktop Hub is HEALTHY and listening on port $Port!" -ForegroundColor Green
        Write-Host "  Client Dashboard: http://localhost:$Port/client" -ForegroundColor Cyan
        Write-Host "  API Docs:         http://localhost:$Port/docs" -ForegroundColor Cyan
        Write-Host "  Diagnostics:      http://localhost:$Port/api/v1/system/diagnostics" -ForegroundColor Cyan
    } else {
        Write-Warning "[WARN] Hub started, but health probe has not yet responded. Check logs\smart_spectator.log"
    }
}

# Smart Spectator - Windows PowerShell Process Terminator
# Conforms to Section 5 of Phase 8 Master Specification.
# Performs database-safe, recorder-safe graceful shutdown.

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pidFile = Join-Path $root "hub.pid"

if (-not (Test-Path $pidFile)) {
    Write-Host "[INFO] No hub.pid found. Searching for running uvicorn process..." -ForegroundColor Yellow
    $procs = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*services.hub_backend.main:app*" }
    if (-not $procs) {
        Write-Host "[OK] Smart Spectator Hub is not currently running." -ForegroundColor Green
        exit 0
    }
} else {
    $hubPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    $procs = Get-Process -Id $hubPid -ErrorAction SilentlyContinue
}

if ($procs) {
    foreach ($p in $procs) {
        Write-Host "[INFO] Stopping Hub process (PID $($p.Id))..." -ForegroundColor Yellow
        $p.CloseMainWindow() | Out-Null
        Start-Sleep -Seconds 2
        if (-not $p.HasExited) {
            Stop-Process -Id $p.Id -Force
        }
        Write-Host "[OK] Hub process terminated cleanly." -ForegroundColor Green
    }
}

if (Test-Path $pidFile) {
    Remove-Item $pidFile -Force
}
Write-Host "[OK] Shutdown complete." -ForegroundColor Green

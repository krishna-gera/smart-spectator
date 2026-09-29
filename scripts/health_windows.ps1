# Smart Spectator - Windows PowerShell Health Check
# Conforms to Sections 4 & 21 of Phase 8 Master Specification.

[CmdletBinding()]
param (
    [int]$Port = 8000
)

$ErrorActionPreference = "SilentlyContinue"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Smart Spectator - Health & Subsystem Status Probe      " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$healthUrl = "http://localhost:$Port/health"
$diagUrl = "http://localhost:$Port/api/v1/system/diagnostics"

$healthResp = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 3
if ($healthResp -and $healthResp.status -eq "healthy") {
    Write-Host "[OK] Liveness: HEALTHY (Uptime: $($healthResp.uptime_seconds)s, Version: $($healthResp.version))" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Liveness probe failed. Hub is STOPPED or UNRESPONSIVE." -ForegroundColor Red
    exit 1
}

$diagResp = Invoke-RestMethod -Uri $diagUrl -TimeoutSec 5
if ($diagResp) {
    Write-Host "`nSubsystem Diagnostic Status:" -ForegroundColor Yellow
    $diagResp.PSObject.Properties | ForEach-Object {
        $name = $_.Name
        $sub = $_.Value
        $st = $sub.status
        if ($st -eq "READY" -or $st -eq "healthy") {
            Write-Host "  [$name]: $st" -ForegroundColor Green
        } elseif ($st -eq "DEGRADED") {
            Write-Host "  [$name]: $st (Warning: $($sub.last_error))" -ForegroundColor Yellow
        } else {
            Write-Host "  [$name]: $st (Error: $($sub.last_error))" -ForegroundColor Red
        }
    }
}
Write-Host "==========================================================" -ForegroundColor Cyan

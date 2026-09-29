# Smart Spectator - Service Status Checker
# Conforms to Section 5 of Phase 8 Master Specification.
# Reports:
#   Hub: RUNNING / STOPPED / FAILED
#   Database: HEALTHY / DEGRADED / FAILED
#   AI: READY / DEGRADED / FAILED
#   Recorder: READY / DEGRADED / FAILED

[CmdletBinding()]
param (
    [int]$Port = 8000
)

$ErrorActionPreference = "SilentlyContinue"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pidFile = Join-Path $root "hub.pid"

$hubStatus = "STOPPED"
$dbStatus = "FAILED"
$aiStatus = "FAILED"
$recStatus = "FAILED"

# 1. Check Hub Process
if (Test-Path $pidFile) {
    $pidNum = Get-Content $pidFile
    $proc = Get-Process -Id $pidNum -ErrorAction SilentlyContinue
    if ($proc) {
        $hubStatus = "RUNNING"
    }
}

# 2. Check HTTP Diagnostics
try {
    $resp = Invoke-RestMethod -Uri "http://localhost:$Port/api/v1/system/diagnostics" -TimeoutSec 3
    if ($resp) {
        $hubStatus = "RUNNING"
        
        # Database
        $dbSub = $resp.database.status
        if ($dbSub -eq "READY") { $dbStatus = "HEALTHY" }
        elseif ($dbSub -eq "DEGRADED") { $dbStatus = "DEGRADED" }
        else { $dbStatus = "FAILED" }

        # AI
        $aiSub = $resp.ai_engine.status
        if ($aiSub -eq "READY") { $aiStatus = "READY" }
        elseif ($aiSub -eq "DEGRADED") { $aiStatus = "DEGRADED" }
        else { $aiStatus = "FAILED" }

        # Recorder
        $recSub = $resp.recorder.status
        if ($recSub -eq "READY") { $recStatus = "READY" }
        elseif ($recSub -eq "DEGRADED") { $recStatus = "DEGRADED" }
        else { $recStatus = "FAILED" }
    }
} catch {
    if ($hubStatus -eq "RUNNING") {
        $hubStatus = "FAILED"
    }
}

Write-Host "Hub:      $hubStatus" -ForegroundColor $(if ($hubStatus -eq "RUNNING") { "Green" } else { "Red" })
Write-Host "Database: $dbStatus" -ForegroundColor $(if ($dbStatus -eq "HEALTHY") { "Green" } elseif ($dbStatus -eq "DEGRADED") { "Yellow" } else { "Red" })
Write-Host "AI:       $aiStatus" -ForegroundColor $(if ($aiStatus -eq "READY") { "Green" } elseif ($aiStatus -eq "DEGRADED") { "Yellow" } else { "Red" })
Write-Host "Recorder: $recStatus" -ForegroundColor $(if ($recStatus -eq "READY") { "Green" } elseif ($recStatus -eq "DEGRADED") { "Yellow" } else { "Red" })

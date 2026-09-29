# Smart Spectator - Windows Uninstaller Script
# Conforms to Section 4 of Phase 8 Master Specification.

[CmdletBinding()]
param (
    [switch]$KeepData,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Smart Spectator - Windows Hub Uninstaller              " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Stop running hub process
$stopScript = Join-Path $PSScriptRoot "stop_windows.ps1"
if (Test-Path $stopScript) {
    & $stopScript
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

# 2. Clean Virtual Environment
$venvDir = Join-Path $root "venv"
if (Test-Path $venvDir) {
    Write-Host "[INFO] Removing virtual environment..." -ForegroundColor Yellow
    Remove-Item $venvDir -Recurse -Force
    Write-Host "[OK] Virtual environment removed." -ForegroundColor Green
}

# 3. Clean temporary files
$pidFile = Join-Path $root "hub.pid"
if (Test-Path $pidFile) { Remove-Item $pidFile -Force }

if (-not $KeepData) {
    $confirm = $Force -or ($Host.UI.PromptForChoice("Clean Storage", "Delete recordings, logs, and database?", @("&Yes", "&No"), 1) -eq 0)
    if ($confirm) {
        Write-Host "[INFO] Purging recordings, logs, and temporary caches..." -ForegroundColor Yellow
        @("logs", "recordings", "snapshots", "backups") | ForEach-Object {
            $p = Join-Path $root $_
            if (Test-Path $p) { Remove-Item $p -Recurse -Force }
        }
        $db = Join-Path $root "smart_spectator.db"
        if (Test-Path $db) { Remove-Item $db -Force }
        Write-Host "[OK] Local data cleaned." -ForegroundColor Green
    }
}

Write-Host "[OK] Uninstallation complete." -ForegroundColor Green

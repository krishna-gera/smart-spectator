"""
Smart Spectator - Health & System Status Endpoints
"""

import time
import os
import psutil
from fastapi import APIRouter
from ..config import settings
from services.device_manager.discovery import get_local_ip
from ..database.connection import db_session

router = APIRouter(tags=["Health & Diagnostics"])
_startup_time = time.time()


@router.get("/health")
def health_check():
    """Liveness probe for local desktop hub."""
    return {
        "status": "healthy",
        "service": "Smart Spectator Desktop Hub",
        "uptime_seconds": round(time.time() - _startup_time, 2),
        "version": "1.0.0"
    }


@router.get("/system/status")
def system_status():
    """System diagnostic metrics: CPU, memory, active cameras, LAN IP."""
    try:
        cpu_usage = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        mem_percent = mem.percent
        mem_used_mb = round(mem.used / (1024 * 1024), 1)
        mem_total_mb = round(mem.total / (1024 * 1024), 1)
    except Exception:
        cpu_usage = 0.0
        mem_percent = 0.0
        mem_used_mb = 0.0
        mem_total_mb = 0.0

    with db_session() as conn:
        cam_count = conn.execute("SELECT COUNT(*) as c FROM cameras WHERE status = 'streaming'").fetchone()["c"]
        paired_count = conn.execute("SELECT COUNT(*) as c FROM devices WHERE status IN ('paired', 'connected')").fetchone()["c"]

    return {
        "hub_ip": get_local_ip(),
        "api_port": settings.PORT,
        "stream_port": settings.STREAM_PORT,
        "cpu_usage_percent": cpu_usage,
        "memory_usage_percent": mem_percent,
        "memory_used_mb": mem_used_mb,
        "memory_total_mb": mem_total_mb,
        "active_streaming_cameras": cam_count,
        "paired_devices_total": paired_count,
        "dev_mode": settings.DEV_MODE
    }

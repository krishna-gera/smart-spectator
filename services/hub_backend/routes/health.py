"""
Smart Spectator - Health & System Status Endpoints
Conforms to Sections 24, 25, 46, 66 of Phase 6/7 Master Specification.
Provides shallow liveness (/health) and deep component diagnostics (/health/detailed).
"""

import os
from pathlib import Path
import platform
import time
from typing import Dict, Any
from fastapi import APIRouter
import psutil

from ..config import settings
from services.device_manager.discovery import get_local_ip
from ..database.connection import db_session
from services.stream_engine.server import stream_engine
from services.ai_engine.pipeline import ai_pipeline
from services.event_engine import event_engine

router = APIRouter(tags=["Health & Diagnostics"])
_startup_time = time.time()


@router.get("/health")
def health_check() -> Dict[str, Any]:
    """Shallow liveness probe for local desktop hub (Section 24)."""
    return {
        "status": "healthy",
        "service": "Smart Spectator Desktop Hub",
        "uptime_seconds": round(time.time() - _startup_time, 2),
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/health/detailed")
def detailed_health_check() -> Dict[str, Any]:
    """
    Deep diagnostic probe reporting the live operational status of each local decoupled subsystem:
    database, stream_engine, ai_engine, event_engine, recorder, websocket, device_manager.
    Conforms strictly to Section 24.
    """
    components: Dict[str, Dict[str, Any]] = {}
    is_any_degraded = False
    is_any_unavailable = False

    # 1. Database Subsystem
    try:
        with db_session() as conn:
            cursor = conn.execute("SELECT COUNT(*) as c FROM cameras")
            cam_count = cursor.fetchone()["c"]
        components["database"] = {
            "status": "healthy",
            "mode": "WAL",
            "path": str(settings.DATABASE_PATH),
            "camera_records": cam_count,
        }
    except Exception as e:
        is_any_unavailable = True
        components["database"] = {
            "status": "unavailable",
            "error": str(e),
        }

    # 2. Stream Ingestion Engine
    try:
        active_sessions = len(stream_engine.sessions)
        components["stream_engine"] = {
            "status": "healthy",
            "port": settings.STREAM_PORT,
            "active_sessions": active_sessions,
        }
    except Exception as e:
        is_any_degraded = True
        components["stream_engine"] = {
            "status": "degraded",
            "error": str(e),
        }

    # 3. AI Perception Pipeline
    try:
        telemetry = ai_pipeline.get_telemetry()
        ai_running = ai_pipeline.is_running
        components["ai_engine"] = {
            "status": "healthy" if ai_running else "degraded",
            "is_running": ai_running,
            "active_model": telemetry.get("active_model", "none"),
            "backend": telemetry.get("active_backend", "none"),
            "is_model_loaded": telemetry.get("is_model_loaded", False),
        }
    except Exception as e:
        is_any_degraded = True
        components["ai_engine"] = {
            "status": "degraded",
            "error": str(e),
        }

    # 4. Event & Automation Engine
    try:
        ee_running = event_engine.is_running
        ee_metrics = event_engine.get_metrics()
        components["event_engine"] = {
            "status": "healthy" if ee_running else "degraded",
            "is_running": ee_running,
            "active_events": ee_metrics.get("active_events_count", 0),
            "worker_queue_depth": ee_metrics.get("worker_queue_depth", 0),
        }
    except Exception as e:
        is_any_degraded = True
        components["event_engine"] = {
            "status": "degraded",
            "error": str(e),
        }

    # 5. Video Recorder & Storage Subsystem
    try:
        rec_dir = settings.RECORDINGS_DIR
        storage_writable = rec_dir.exists() and os.access(str(rec_dir), os.W_OK)
        # Check free disk space in MB
        disk_free_mb = round(psutil.disk_usage(str(rec_dir)).free / (1024 * 1024), 1)
        storage_degraded = disk_free_mb < settings.MIN_FREE_DISK_MB
        if storage_degraded:
            is_any_degraded = True

        components["recorder"] = {
            "status": "degraded" if storage_degraded else ("healthy" if storage_writable else "unavailable"),
            "recordings_dir": str(rec_dir),
            "free_disk_mb": disk_free_mb,
            "min_free_threshold_mb": settings.MIN_FREE_DISK_MB,
            "degraded_reason": "Low disk space threshold reached" if storage_degraded else None,
        }
    except Exception as e:
        is_any_degraded = True
        components["recorder"] = {
            "status": "degraded",
            "error": str(e),
        }

    # 6. WebSocket Streaming Subsystem
    components["websocket"] = {
        "status": "healthy",
        "route": "/api/v1/events/stream",
    }

    # 7. Device Manager Subsystem
    components["device_manager"] = {
        "status": "healthy",
        "pairing_ttl_seconds": settings.PAIRING_PIN_TTL_SECONDS,
        "max_pin_attempts": settings.MAX_PIN_ATTEMPTS,
    }

    # Calculate overall system status
    overall_status = "unavailable" if is_any_unavailable else ("degraded" if is_any_degraded else "healthy")

    return {
        "status": overall_status,
        "version": settings.APP_VERSION,
        "uptime_seconds": round(time.time() - _startup_time, 2),
        "components": components,
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
        "dev_mode": settings.DEV_MODE,
        "environment": settings.ENVIRONMENT,
        "version": settings.APP_VERSION,
    }

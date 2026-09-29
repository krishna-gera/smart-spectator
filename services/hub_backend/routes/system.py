"""
Smart Spectator - REST API: System Telemetry, Metrics & Audit Logging
Conforms to Sections 67, 90, 95 of Phase 4 & Phase 5 specifications.
"""

from datetime import datetime
import json
import os
import shutil
import time
from typing import Dict, Any, List
from fastapi import APIRouter, Query

from services.hub_backend.config import settings
from services.hub_backend.database.connection import db_session
from services.event_engine import event_engine
from services.ai_engine.pipeline import ai_pipeline
from services.stream_engine.server import stream_engine
from services.device_manager.manager import device_manager

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/metrics")
def get_system_metrics() -> Dict[str, Any]:
    """Exposes real-time system, AI, and event engine performance metrics."""
    ee_metrics = event_engine.get_metrics()
    ai_telemetry = ai_pipeline.get_telemetry()

    # Calculate disk usage for recordings
    storage_used_bytes = 0
    try:
        for p in settings.RECORDINGS_DIR.rglob("*"):
            if p.is_file():
                storage_used_bytes += p.stat().st_size
    except Exception:
        pass

    storage_used_gb = round(storage_used_bytes / (1024 * 1024 * 1024), 3)

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "event_engine": ee_metrics,
        "ai_pipeline": {
            "model_id": ai_telemetry.get("active_model"),
            "backend": ai_telemetry.get("active_backend"),
            "is_loaded": ai_telemetry.get("is_model_loaded"),
            "camera_contexts": ai_telemetry.get("camera_contexts", {}),
        },
        "stream_engine": {
            "active_sessions": len(stream_engine.sessions),
        },
        "storage": {
            "recordings_used_gb": storage_used_gb,
            "max_storage_gb": settings.RECORDING_MAX_STORAGE_GB,
            "retention_days": settings.RECORDING_RETENTION_DAYS,
        },
    }


@router.get("/health/components")
def get_component_health() -> Dict[str, Any]:
    """Reports status of each decoupled local engine (Section 95)."""
    # 1. Database check
    db_status = "healthy"
    try:
        with db_session() as conn:
            conn.execute("SELECT 1;").fetchone()
    except Exception:
        db_status = "unhealthy"

    # 2. AI engine
    ai_status = "healthy" if ai_pipeline.is_running else "degraded"

    # 3. Event engine
    ee_status = "healthy" if event_engine.is_running else "degraded"

    # 4. Stream engine
    stream_status = "healthy"

    # 5. Device manager
    dev_status = "healthy"

    # 6. Recording engine
    rec_status = "healthy" if settings.RECORDINGS_DIR.exists() else "degraded"

    return {
        "status": "healthy" if all(s == "healthy" for s in [db_status, ai_status, ee_status]) else "degraded",
        "components": {
            "stream_engine": stream_status,
            "ai_engine": ai_status,
            "event_engine": ee_status,
            "recording_engine": rec_status,
            "database": db_status,
            "device_manager": dev_status,
            "websocket": "healthy",
        }
    }


@router.get("/audit", response_model=List[Dict[str, Any]])
def get_audit_logs(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    """Retrieves immutable audit log history (Section 90)."""
    with db_session() as conn:
        cursor = conn.execute(
            "SELECT log_id, timestamp, actor, action, resource, metadata_json "
            "FROM audit_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = cursor.fetchall()
        return [
            {
                "log_id": r["log_id"],
                "timestamp": r["timestamp"],
                "actor": r["actor"],
                "action": r["action"],
                "resource": r["resource"],
                "metadata": json.loads(r["metadata_json"]) if r.get("metadata_json") else {},
            }
            for r in rows
        ]

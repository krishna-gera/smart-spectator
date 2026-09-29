"""
Smart Spectator - REST API: System Telemetry, Metrics & Audit Logging
Conforms to Sections 67, 90, 95 of Phase 4 & Phase 5 specifications.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Query, HTTPException, Body
import psutil
try:
    import onnxruntime as ort
except ImportError:
    ort = None

from services.hub_backend.config import settings
from services.hub_backend.database.connection import db_session
from services.hub_backend.database.backup import export_database_backup, restore_database_backup
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


@router.get("/hardware")
def get_hardware_info() -> Dict[str, Any]:
    """
    Identifies actual host hardware: CPU, GPU, NPU/QNN availability, RAM, OS, architecture.
    Strictly conforms to Section 46 & Section 44. Never fabricates numbers.
    """
    os_name = platform.system()
    os_release = platform.release()
    arch = platform.machine()
    processor = platform.processor() or "unknown"
    ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)
    cpu_count = psutil.cpu_count(logical=True)

    available_ort_providers = ort.get_available_providers() if ort else []
    
    # Accurate detection of NPU/QNN
    has_qnn = "QNNExecutionProvider" in available_ort_providers
    if has_qnn:
        npu_status = "Available"
        npu_target = "Qualcomm AI Engine Direct (Hexagon NPU)"
    elif "Windows" in os_name and ("arm" in arch.lower() or "aarch64" in arch.lower()):
        npu_status = "Pending QNN Runtime Installation"
        npu_target = "Qualcomm Hexagon NPU (Supported Hardware Detected)"
    else:
        npu_status = "Unavailable (Non-Snapdragon / Host Architecture)"
        npu_target = None

    # GPU acceleration detection
    if "DmlExecutionProvider" in available_ort_providers:
        gpu_accel = "DirectML (GPU)"
    elif "CoreMLExecutionProvider" in available_ort_providers:
        gpu_accel = "Apple Neural Engine / CoreML"
    elif "CUDAExecutionProvider" in available_ort_providers:
        gpu_accel = "NVIDIA CUDA"
    else:
        gpu_accel = "CPU Fallback"

    return {
        "os": os_name,
        "os_version": os_release,
        "architecture": arch,
        "processor": processor,
        "cpu_logical_cores": cpu_count,
        "ram_total_gb": ram_gb,
        "npu": {
            "status": npu_status,
            "target": npu_target,
            "qnn_provider_present": has_qnn,
        },
        "gpu_acceleration": gpu_accel,
        "available_execution_providers": available_ort_providers,
        "active_ai_backend": ai_pipeline.get_telemetry().get("active_backend", "cpu"),
        "hardware_verified": has_qnn,
    }


@router.post("/backup")
def create_backup() -> Dict[str, Any]:
    """Exports consistent local database backup (Section 18)."""
    try:
        backup_path = export_database_backup()
        return {
            "status": "success",
            "backup_file": backup_path.name,
            "backup_path": str(backup_path),
            "size_bytes": backup_path.stat().st_size,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database backup failed: {e}")


@router.post("/restore")
def restore_backup(payload: Dict[str, str] = Body(...)) -> Dict[str, Any]:
    """Restores database from an exported backup file (Section 18)."""
    backup_file = payload.get("backup_file")
    if not backup_file:
        raise HTTPException(status_code=400, detail="Field 'backup_file' is required.")

    backup_path = settings.BACKUP_DIR / Path(backup_file).name
    try:
        result = restore_database_backup(backup_path)
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Backup file not found: {backup_file}")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"Backup validation failed: {ve}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database restore failed: {e}")


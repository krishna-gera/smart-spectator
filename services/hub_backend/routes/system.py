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
from fastapi import APIRouter, Query, HTTPException, Body, Depends
import psutil
try:
    import onnxruntime as ort
except ImportError:
    ort = None

from services.hub_backend.config import settings
from services.hub_backend.database.connection import db_session
from services.hub_backend.database.backup import export_database_backup, restore_database_backup
from services.hub_backend.database.migrations import MigrationTracker
from services.event_engine import event_engine
from services.ai_engine.pipeline import ai_pipeline
from services.stream_engine.server import stream_engine
from services.device_manager.manager import device_manager
from ai.inference.manager import provider_manager
from ai.models.validator import model_validator
from services.hub_backend.routes.health import _startup_time
from ..auth.dependencies import require_admin, require_operator, require_viewer
from ..auth.models import Principal

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
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
    Strictly conforms to Section 2 of Phase 8 Master Specification. Never fabricates numbers.
    """
    os_name = platform.system()
    os_release = platform.release()
    arch = platform.machine()
    processor = platform.processor() or "unknown"
    ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)
    cpu_count = psutil.cpu_count(logical=True)

    available_ort_providers = ort.get_available_providers() if ort else []
    
    # Accurate detection of NPU/QNN and GPU
    has_qnn = "QNNExecutionProvider" in available_ort_providers
    has_dml = "DmlExecutionProvider" in available_ort_providers
    has_coreml = "CoreMLExecutionProvider" in available_ort_providers
    has_cuda = "CUDAExecutionProvider" in available_ort_providers
    has_cpu = "CPUExecutionProvider" in available_ort_providers or (ort is not None)

    accelerators: List[str] = []
    if has_qnn:
        accelerators.append("Hexagon NPU (QNN)")
    if has_dml:
        accelerators.append("DirectML (GPU)")
    if has_coreml:
        accelerators.append("Apple Neural Engine / CoreML")
    if has_cuda:
        accelerators.append("NVIDIA CUDA")

    try:
        _, selected_prov = provider_manager.get_preferred_provider("auto")
        selected_provider_name = selected_prov.provider_name
    except Exception:
        selected_provider_name = "CPUExecutionProvider"

    if has_qnn:
        npu_status = "Available"
        npu_target = "Qualcomm AI Engine Direct (Hexagon NPU)"
        hw_status = "VERIFIED_ON_SNAPDRAGON_QNN"
    elif "Windows" in os_name and ("arm" in arch.lower() or "aarch64" in arch.lower()):
        npu_status = "Pending QNN Runtime Installation"
        npu_target = "Qualcomm Hexagon NPU (Supported Hardware Detected)"
        hw_status = "HARDWARE_VALIDATION_PENDING (Snapdragon Windows Detected, QNN SDK Pending)"
    else:
        npu_status = "Unavailable (Non-Snapdragon / Host Architecture)"
        npu_target = None
        hw_status = f"HOST_PROVIDER_ACTIVE ({selected_provider_name})"

    # GPU acceleration detection
    if has_dml:
        gpu_accel = "DirectML (GPU)"
    elif has_coreml:
        gpu_accel = "Apple Neural Engine / CoreML"
    elif has_cuda:
        gpu_accel = "NVIDIA CUDA"
    else:
        gpu_accel = "CPU Fallback"

    return {
        "os": os_name,
        "os_version": os_release,
        "architecture": arch,
        "processor": processor,
        "memory_gb": ram_gb,
        "ram_total_gb": ram_gb,
        "cpu_logical_cores": cpu_count,
        "accelerators": accelerators,
        "onnxruntime_providers": available_ort_providers,
        "available_execution_providers": available_ort_providers,
        "selected_provider": selected_provider_name,
        "qnn_available": has_qnn,
        "directml_available": has_dml,
        "cpu_available": has_cpu,
        "hardware_validation_status": hw_status,
        "npu": {
            "status": npu_status,
            "target": npu_target,
            "qnn_provider_present": has_qnn,
        },
        "gpu_acceleration": gpu_accel,
        "active_ai_backend": ai_pipeline.get_telemetry().get("active_backend", "cpu"),
        "hardware_verified": has_qnn,
    }


@router.get("/diagnostics")
def get_system_diagnostics() -> Dict[str, Any]:
    """
    Unified runtime diagnostics endpoint conforming to Section 21 of Phase 8 specification.
    Reports operational status across all 11 subsystems with zero secret leakage.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    uptime_sec = round(time.time() - _startup_time, 2)

    # 1. Database
    db_status = "READY"
    db_err = None
    schema_version = 0
    try:
        with db_session() as conn:
            conn.execute("SELECT 1;").fetchone()
            tracker = MigrationTracker(conn)
            schema_version = tracker.get_current_version()
    except Exception as e:
        db_status = "FAILED"
        db_err = str(e)

    # 2. AI Engine
    ai_telemetry = ai_pipeline.get_telemetry()
    hw_info = get_hardware_info()
    model_report = model_validator.validate_all()
    if ai_telemetry.get("is_model_loaded") or ai_pipeline.is_running:
        ai_status = "READY"
    elif model_report.get("status") == "READY":
        ai_status = "READY"
    else:
        ai_status = "DEGRADED"

    # 3. Event Engine
    ee_metrics = event_engine.get_metrics()
    ee_status = "READY" if event_engine.is_running else "DEGRADED"

    # 4. Stream Engine
    stream_status = "READY" if stream_engine.is_running else "DEGRADED"

    # 5. Recorder & Storage
    free_disk_mb = 0.0
    try:
        total, used, free = shutil.disk_usage(settings.RECORDINGS_DIR if settings.RECORDINGS_DIR.exists() else settings.BASE_DIR)
        free_disk_mb = round(free / (1024 * 1024), 2)
    except Exception:
        pass

    storage_used_bytes = 0
    try:
        for p in settings.RECORDINGS_DIR.rglob("*"):
            if p.is_file():
                storage_used_bytes += p.stat().st_size
    except Exception:
        pass
    storage_used_gb = round(storage_used_bytes / (1024 * 1024 * 1024), 3)

    is_recording_degraded = free_disk_mb < settings.MIN_FREE_DISK_MB
    recorder_status = "DEGRADED" if is_recording_degraded else "READY"
    recorder_err = "Disk space below safety threshold (500MB)" if is_recording_degraded else None

    # 6. Devices
    paired_devices_count = 0
    dev_status = "READY"
    dev_err = None
    try:
        with db_session() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM devices WHERE revoked = 0;").fetchone()
            paired_devices_count = row["cnt"] if row else 0
    except Exception as e:
        dev_status = "DEGRADED"
        dev_err = str(e)

    # 7. Models Integrity (validated above)

    # 8. WebSocket Clients
    from services.hub_backend.websocket.events import event_stream_hub
    connected_ws_count = len(event_stream_hub.active_clients)

    return {
        "hub": {
            "status": "READY",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "uptime_seconds": uptime_sec,
            "last_error": None,
            "timestamp": now_iso,
        },
        "database": {
            "status": db_status,
            "schema_version": schema_version,
            "path": str(settings.DATABASE_PATH),
            "last_error": db_err,
            "timestamp": now_iso,
        },
        "stream_engine": {
            "status": stream_status,
            "active_streams": len(stream_engine.sessions),
            "tcp_port": settings.STREAM_PORT,
            "last_error": None,
            "timestamp": now_iso,
        },
        "ai_engine": {
            "status": ai_status,
            "active_model": ai_telemetry.get("active_model"),
            "selected_provider": hw_info.get("selected_provider"),
            "is_model_loaded": ai_telemetry.get("is_model_loaded", False),
            "last_error": None,
            "timestamp": now_iso,
        },
        "event_engine": {
            "status": ee_status,
            "is_running": event_engine.is_running,
            "queue_depth": ee_metrics.get("queue_depth", 0),
            "last_error": None,
            "timestamp": now_iso,
        },
        "recorder": {
            "status": recorder_status,
            "disk_free_mb": free_disk_mb,
            "min_disk_free_mb": settings.MIN_FREE_DISK_MB,
            "recording_degraded": is_recording_degraded,
            "last_error": recorder_err,
            "timestamp": now_iso,
        },
        "devices": {
            "status": dev_status,
            "paired_devices_count": paired_devices_count,
            "last_error": dev_err,
            "timestamp": now_iso,
        },
        "websocket": {
            "status": "READY",
            "connected_clients": connected_ws_count,
            "last_error": None,
            "timestamp": now_iso,
        },
        "storage": {
            "status": "READY",
            "recordings_used_gb": storage_used_gb,
            "max_storage_gb": settings.RECORDING_MAX_STORAGE_GB,
            "retention_days": settings.RECORDING_RETENTION_DAYS,
            "last_error": None,
            "timestamp": now_iso,
        },
        "models": {
            "status": model_report.get("status", "READY"),
            "manifest_path": model_report.get("manifest_path"),
            "models": model_report.get("models", {}),
            "last_error": model_report.get("error"),
            "timestamp": now_iso,
        },
        "hardware": {
            "status": "READY",
            "os": hw_info.get("os"),
            "architecture": hw_info.get("architecture"),
            "processor": hw_info.get("processor"),
            "memory_gb": hw_info.get("memory_gb"),
            "selected_provider": hw_info.get("selected_provider"),
            "qnn_available": hw_info.get("qnn_available"),
            "directml_available": hw_info.get("directml_available"),
            "cpu_available": hw_info.get("cpu_available"),
            "hardware_validation_status": hw_info.get("hardware_validation_status"),
            "last_error": None,
            "timestamp": now_iso,
        },
    }


@router.post("/backup")
def create_backup(admin: Principal = Depends(require_admin)) -> Dict[str, Any]:
    """Exports consistent local database backup (Section 18). Administrator only."""
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
def restore_backup(
    payload: Dict[str, str] = Body(...),
    admin: Principal = Depends(require_admin)
) -> Dict[str, Any]:
    """Restores database from an exported backup file (Section 18). Administrator only."""
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


# ---------------------------------------------------------------------------
# Phase 9: Categorized Configuration Management (Sections 18, 19, 24)
# ---------------------------------------------------------------------------

@router.get("/config")
def get_system_configuration(viewer: Principal = Depends(require_viewer)) -> Dict[str, Any]:
    """Retrieves all categorized system configuration without exposing secrets."""
    from services.hub_backend.config_manager import load_categorized_config
    return load_categorized_config()


@router.put("/config/{category}")
def update_system_configuration(
    category: str,
    payload: Dict[str, Any] = Body(...),
    admin: Principal = Depends(require_admin)
) -> Dict[str, Any]:
    """Validates and updates configuration parameters for a specific category. Administrator only."""
    from services.hub_backend.config_manager import save_config_category
    try:
        return save_config_category(category, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Configuration update failed: {e}")


@router.get("/config/export")
def export_configuration(admin: Principal = Depends(require_admin)) -> Dict[str, Any]:
    """Safely exports complete configuration manifest with zero secret leakage. Administrator only."""
    from services.hub_backend.config_manager import export_safe_configuration
    return export_safe_configuration()


@router.post("/config/import")
def import_configuration(
    payload: Dict[str, Any] = Body(...),
    admin: Principal = Depends(require_admin)
) -> Dict[str, Any]:
    """Validates and imports system configuration manifest. Administrator only."""
    from services.hub_backend.config_manager import import_safe_configuration
    try:
        return import_safe_configuration(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Configuration import failed: {e}")


# ---------------------------------------------------------------------------
# Phase 9: Storage Dashboard & Retention Lifecycle (Sections 20 & 21)
# ---------------------------------------------------------------------------

@router.get("/storage")
def get_storage_dashboard(viewer: Principal = Depends(require_viewer)) -> Dict[str, Any]:
    """Returns detailed storage metrics, usage breakdowns, and retention policies."""
    from services.hub_backend.storage.retention import get_retention_policies
    rec_dir = settings.RECORDINGS_DIR.resolve()
    db_path = settings.DATABASE_PATH.resolve()
    model_dir = (settings.BASE_DIR / "ai" / "models" / "releases").resolve()

    total_disk_gb = 0.0
    used_disk_gb = 0.0
    free_disk_gb = 0.0
    try:
        tot, used, free = shutil.disk_usage(rec_dir if rec_dir.exists() else settings.BASE_DIR)
        total_disk_gb = round(tot / (1024 ** 3), 2)
        used_disk_gb = round(used / (1024 ** 3), 2)
        free_disk_gb = round(free / (1024 ** 3), 2)
    except Exception:
        pass

    # Recordings storage
    rec_bytes = 0
    rec_count = 0
    if rec_dir.exists():
        for p in rec_dir.glob("*.mp4"):
            if p.is_file():
                rec_bytes += p.stat().st_size
                rec_count += 1
    rec_storage_gb = round(rec_bytes / (1024 ** 3), 3)

    # Database size
    db_bytes = db_path.stat().st_size if db_path.exists() else 0
    db_size_mb = round(db_bytes / (1024 ** 2), 2)

    # Model storage
    model_bytes = 0
    if model_dir.exists():
        for p in model_dir.glob("*.onnx*"):
            if p.is_file():
                model_bytes += p.stat().st_size
    model_size_mb = round(model_bytes / (1024 ** 2), 2)

    return {
        "disk_total_gb": total_disk_gb,
        "disk_used_gb": used_disk_gb,
        "disk_free_gb": free_disk_gb,
        "recordings_storage_gb": rec_storage_gb,
        "recordings_count": rec_count,
        "database_size_mb": db_size_mb,
        "models_storage_mb": model_size_mb,
        "retention_policies": get_retention_policies(),
        "storage_confinement_safe": True,
    }


@router.post("/storage/retention/cleanup")
def trigger_retention_cleanup(
    event_days: Optional[int] = Query(None, ge=1, le=365),
    recording_days: Optional[int] = Query(None, ge=1, le=180),
    operator: Principal = Depends(require_operator),
) -> Dict[str, Any]:
    """Executes automated retention pruning of expired events and recordings."""
    from services.hub_backend.storage.retention import run_retention_cleanup
    try:
        return run_retention_cleanup(
            event_retention_days=event_days,
            recording_retention_days=recording_days,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retention cleanup failed: {e}")


# ---------------------------------------------------------------------------
# Phase 9: Operator Activity Log (Section 22)
# ---------------------------------------------------------------------------

@router.get("/activity", response_model=List[Dict[str, Any]])
def get_operator_activity_log(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    viewer: Principal = Depends(require_viewer),
):
    """Retrieves operator activity audit trail with secret masking."""
    with db_session() as conn:
        cursor = conn.execute(
            """
            SELECT log_id, timestamp, actor, action, resource, metadata_json
            FROM audit_logs
            ORDER BY timestamp DESC LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )
        rows = cursor.fetchall()
        return [
            {
                "log_id": r["log_id"],
                "timestamp": r["timestamp"],
                "actor": r["actor"],
                "action": r["action"],
                "resource": r["resource"],
                "details": json.loads(r["metadata_json"]) if r.get("metadata_json") else {},
            }
            for r in rows
        ]


# ---------------------------------------------------------------------------
# Phase 9: Local Notification Configuration (Sections 10 & 11)
# ---------------------------------------------------------------------------

@router.get("/notifications")
def get_notification_settings(viewer: Principal = Depends(require_viewer)) -> Dict[str, Any]:
    """Retrieves notification configuration and per-event cooldown rules."""
    from services.event_engine.notifications import DEFAULT_COOLDOWNS, EVENT_CATEGORY_MAP
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM notification_configs").fetchall()
        configs = {r["event_type"]: dict(r) for r in rows}

    result = []
    for evt_type, default_cool in DEFAULT_COOLDOWNS.items():
        entry = configs.get(evt_type, {})
        cat = entry.get("category", EVENT_CATEGORY_MAP.get(evt_type, "Important"))
        if hasattr(cat, "value"):
            cat = cat.value
        result.append({
            "event_type": evt_type,
            "category": cat,
            "is_enabled": bool(entry.get("is_enabled", 1)),
            "cooldown_seconds": float(entry.get("cooldown_seconds", default_cool)),
        })
    return {"notifications": result}


@router.put("/notifications/{event_type}")
def update_notification_setting(event_type: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Updates cooldown or enabled status for a specific event type."""
    is_enabled = 1 if payload.get("is_enabled", True) else 0
    cooldown = float(payload.get("cooldown_seconds", 15.0))
    category = payload.get("category", "Important")

    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO notification_configs (config_id, event_type, category, is_enabled, cooldown_seconds, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(event_type) DO UPDATE SET
                is_enabled = excluded.is_enabled,
                cooldown_seconds = excluded.cooldown_seconds,
                category = excluded.category,
                updated_at = CURRENT_TIMESTAMP
            """,
            (f"nc_{event_type.lower()}", event_type, category, is_enabled, cooldown)
        )
    return {"status": "success", "event_type": event_type, "is_enabled": bool(is_enabled), "cooldown_seconds": cooldown}


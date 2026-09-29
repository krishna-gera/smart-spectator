from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, status, Query, Body
from services.ai_engine.pipeline import ai_pipeline
from ai.inference.manager import provider_manager
from ai.models.registry import model_registry
from ai.models.ab_evaluator import ab_evaluator
from ai.models.validator import model_validator

router = APIRouter(prefix="/ai", tags=["AI Perception & Telemetry"])


@router.get("/status", status_code=status.HTTP_200_OK)
def get_ai_status():
    """
    Returns comprehensive AI perception engine diagnostics conforming to Section 15:
    Detector, Tracker, Temporal Model, Provider, Model version, Checksum,
    Input FPS, Inference FPS, Latency, Queue depth, Dropped frames, and Integrity.
    """
    detected_backends = [b.value for b in provider_manager.detect_available_backends()]
    telemetry = ai_pipeline.get_telemetry()
    perf = ai_pipeline.detector.get_performance()

    # Determine actual hardware provider
    raw_backend = telemetry.get("active_backend", "cpu")
    if "qnn" in raw_backend:
        actual_provider_type = "QNN"
    elif any(gpu in raw_backend for gpu in ["directml", "coreml", "cuda"]):
        actual_provider_type = "GPU"
    else:
        actual_provider_type = "CPU"

    # Aggregated camera queue and frame stats
    total_frames_received = sum(c.get("frames_received", 0) for c in telemetry.get("camera_contexts", {}).values())
    total_frames_sampled = sum(c.get("frames_sampled", 0) for c in telemetry.get("camera_contexts", {}).values())
    total_frames_dropped = sum(c.get("frames_dropped", 0) for c in telemetry.get("camera_contexts", {}).values())
    avg_latency = (
        round(sum(c.get("latency_ms", 0.0) for c in telemetry.get("camera_contexts", {}).values()) / max(1, len(telemetry.get("camera_contexts", {}))), 2)
        if telemetry.get("camera_contexts") else perf.get("mean_ms", 0.0)
    )

    val_report = model_validator.validate_all()
    models_status = val_report.get("status", "READY")

    return {
        "status": "READY" if (ai_pipeline.is_running or telemetry.get("is_model_loaded")) else "DEGRADED",
        "detector": {
            "name": "YOLOv8-Nano Spatial Detector",
            "version": "8.0.0",
            "model_id": telemetry.get("active_model", "detector_v1"),
            "resolution": [1, 3, 640, 640],
            "integrity": val_report.get("models", {}).get("detector_v1.onnx", {}).get("status", "PASS"),
        },
        "tracker": {
            "name": "ByteTrack Multi-Object Tracker",
            "algorithm": "Kalman Filter + Hungarian IoU matching",
            "isolated_contexts": len(ai_pipeline.contexts),
        },
        "temporal_model": {
            "name": "SpectatorNet Recurrent Sequence Classifier",
            "version": "1.0.0",
            "model_id": model_registry.get_active_production_model("temporal_event").id if model_registry.get_active_production_model("temporal_event") else "spectatornet_v1_int8",
            "precision": model_registry.get_active_production_model("temporal_event").precision if model_registry.get_active_production_model("temporal_event") else "INT8",
            "integrity": val_report.get("models", {}).get("spectatornet_v1_int8.onnx", {}).get("status", "PASS"),
        },
        "provider": actual_provider_type,
        "raw_execution_provider": telemetry.get("active_backend"),
        "supported_backends_detected": detected_backends,
        "input_fps": round(total_frames_received / max(1, len(ai_pipeline.contexts)), 1) if ai_pipeline.contexts else 0.0,
        "inference_fps": perf.get("fps", 0.0),
        "latency_ms": avg_latency,
        "p50_latency_ms": perf.get("p50_ms", 0.0),
        "p95_latency_ms": perf.get("p95_ms", 0.0),
        "queue_depth": sum(ctx.queue.qsize() for ctx in ai_pipeline.contexts.values()),
        "dropped_frames": total_frames_dropped,
        "models_integrity_status": models_status,
        "camera_contexts": telemetry["camera_contexts"],
    }


@router.get("/models", response_model=List[Dict[str, Any]])
def list_registered_models(task_type: Optional[str] = Query(None)):
    """Lists all locally registered AI models and their validation status."""
    return model_registry.list_models(task_type=task_type)


@router.get("/models/{model_id}", response_model=Dict[str, Any])
def get_model_details(model_id: str):
    """Retrieves metadata and validation status for a registered model."""
    m = model_registry.get_model(model_id)
    if not m:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found in registry.")
    from dataclasses import asdict
    return asdict(m)


@router.post("/models/{task_type}/activate")
def activate_production_model(task_type: str, payload: Dict[str, str] = Body(...)):
    """Explicitly selects the active production model for detection or temporal events."""
    model_id = payload.get("model_id")
    if not model_id:
        raise HTTPException(status_code=400, detail="Field 'model_id' is required.")

    try:
        model_registry.set_production_model(task_type, model_id)
        return {
            "status": "success",
            "task_type": task_type,
            "active_production_model": model_id,
            "message": f"Model '{model_id}' activated for task '{task_type}'."
        }
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found in registry.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ab-evaluate", response_model=Dict[str, Any])
def run_model_ab_evaluation(
    model_a_id: str = Query("spectatornet_v1_fp32"),
    model_b_id: str = Query("spectatornet_v1_int8"),
    iterations: int = Query(50, ge=10, le=200),
):
    """Executes offline A/B evaluation benchmarking two models on local hardware."""
    try:
        return ab_evaluator.evaluate_temporal_models(
            model_a_id=model_a_id,
            model_b_id=model_b_id,
            iterations=iterations,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"A/B evaluation failed: {e}")


@router.get("/cameras/{camera_id}/detections", status_code=status.HTTP_200_OK)
def get_latest_camera_detections(camera_id: str):
    """Returns the most recent spatial-temporal Observation for a specific camera."""
    ctx = ai_pipeline.contexts.get(camera_id)
    if not ctx or not ctx.latest_observation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No AI observations available yet for camera '{camera_id}'"
        )
    return ctx.latest_observation

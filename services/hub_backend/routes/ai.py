"""
Smart Spectator - AI Perception & Status Routes
Implements Section 33 & Section 26: Performance telemetry and observation endpoints
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status
from services.ai_engine.pipeline import ai_pipeline
from ai.inference.manager import provider_manager

router = APIRouter(prefix="/ai", tags=["AI Perception & Telemetry"])


@router.get("/status", status_code=status.HTTP_200_OK)
def get_ai_status():
    """
    Returns live AI perception engine telemetry:
    Active model, active execution provider, inference latency (ms),
    inference FPS, and detected hardware accelerators.
    """
    detected_backends = [b.value for b in provider_manager.detect_available_backends()]
    telemetry = ai_pipeline.get_telemetry()
    perf = ai_pipeline.detector.get_performance()

    return {
        "status": "online" if ai_pipeline.is_running else "offline",
        "active_model": telemetry["active_model"],
        "active_backend": telemetry["active_backend"],
        "supported_backends_detected": detected_backends,
        "mean_inference_latency_ms": perf.get("mean_ms", 0.0),
        "p50_latency_ms": perf.get("p50_ms", 0.0),
        "p95_latency_ms": perf.get("p95_ms", 0.0),
        "inference_fps": perf.get("fps", 0.0),
        "camera_contexts": telemetry["camera_contexts"]
    }


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

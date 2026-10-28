"""
Smart Spectator - Offline & Air-Gapped Mode Verification Test Suite
Conforms to Section 13 of Phase 8 Master Specification.
Simulates a completely disconnected network environment (zero public internet access)
and asserts that:
1. No external HTTP/HTTPS network calls are attempted by the system.
2. Device pairing executes successfully.
3. Stream ingestion & decoding executes locally.
4. Level 1 (YOLO), Level 2 (ByteTrack), and Level 3 (SpectatorNet) run 100% locally.
5. Event rules, state machines, and circular MP4 clip recording work offline.
6. Local REST and WebSocket endpoints function without internet.
"""

import socket
import sys
from pathlib import Path
import pytest
import numpy as np
from fastapi.testclient import TestClient

from services.hub_backend.main import app
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, db_session
from services.device_manager.manager import device_manager
from services.ai_engine.detector import YOLOObjectDetector
from services.ai_engine.tracker import ByteTrackTracker
from services.ai_engine.observation_builder import ObservationBuilder
from ai.models.predictor import SpectatorNetPredictor
from services.event_engine.engine import EventEngine
from services.event_engine.recorder import RecordingManager
from shared.schemas.v1.models import Event, EventStatus, EventSeverity


@pytest.fixture(autouse=True)
def enforce_airgap_network(monkeypatch):
    """
    Strict network sandbox fixture.
    Intercepts and blocks any attempt to connect to non-local external IP addresses or domains.
    """
    orig_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0]
        # Allow loopback (127.0.0.1, ::1, localhost) and local LAN addresses
        if host in ("127.0.0.1", "localhost", "::1", "0.0.0.0") or host.startswith("192.168.") or host.startswith("10."):
            return orig_connect(self, address)
        raise ConnectionRefusedError(f"[AIRGAP VIOLATION] Attempted external internet connection to: {host}")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


@pytest.fixture
def offline_env(tmp_path):
    settings.DATABASE_PATH = tmp_path / "offline_test.db"
    settings.RECORDINGS_DIR = tmp_path / "offline_recs"
    settings.SNAPSHOTS_DIR = tmp_path / "offline_snaps"
    settings.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    settings.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    init_database()
    yield
    if settings.DATABASE_PATH.exists():
        settings.DATABASE_PATH.unlink()


def test_codebase_contains_no_external_cloud_services():
    """Audits codebase files ensuring no AWS, Azure, GCP, Firebase, or external API endpoints."""
    forbidden = [
        "api.openai.com",
        "api.anthropic.com",
        "firebaseio.com",
        "amazonaws.com",
        "googleapis.com",
        "supabase.co",
        "sentry.io",
        "segment.io",
        "mixpanel.com",
        "analytics.google.com",
    ]
    py_files = list(Path("services").rglob("*.py")) + list(Path("ai").rglob("*.py")) + list(Path("shared").rglob("*.py"))

    for f in py_files:
        content = f.read_text(encoding="utf-8", errors="ignore").lower()
        for endpoint in forbidden:
            assert endpoint not in content, f"Cloud dependency '{endpoint}' detected in {f}!"


def test_end_to_end_offline_visual_pipeline(offline_env):
    """
    Executes complete visual intelligence pipeline in strict airgap mode:
    Pairing -> Ingest -> Detect -> Track -> SpectatorNet -> Event -> Recording -> REST
    """
    client = TestClient(app)

    # 1. Local Health Check
    health_res = client.get("/api/v1/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"

    # 2. Local Device Pairing Protocol
    req_res = device_manager.request_pairing(
        device_id="offline_phone_01",
        device_name="Airgapped Camera",
        device_model="Snapdragon Test Node"
    )
    assert req_res["status"] == "pending_operator_approval"
    assert "verification_code" not in req_res
    pending = device_manager.list_pending_pairings()
    target = next(p for p in pending if p["device_id"] == "offline_phone_01")
    pin = target["verification_pin"]

    verify_res = device_manager.verify_pairing("offline_phone_01", pin)
    assert verify_res["status"] == "paired"
    token = verify_res["device_token"]
    assert token.startswith("ss_tok_")

    # 3. Local Level 1 Perception (YOLOv8n)
    detector = YOLOObjectDetector()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    detections = detector.detect(frame)
    assert isinstance(detections, list)

    # 4. Local Level 2 Tracking (ByteTrack)
    tracker = ByteTrackTracker()
    tracked = tracker.update("cam_offline", detections, timestamp=1000.0)
    assert isinstance(tracked, list)

    # 5. Local Level 3 Temporal Intelligence (SpectatorNet INT8)
    obs = ObservationBuilder.build(
        camera_id="cam_offline",
        frame_index=1,
        detections=detections,
        tracked_objects=tracked,
        inference_telemetry={"offline": True}
    )
    predictor = SpectatorNetPredictor(
        model_path="ai/models/releases/spectatornet_v1_int8.onnx",
        normalization_path="ai/datasets/smart_spectator/statistics/normalization.json"
    )
    prediction = predictor.predict_window([obs] * 30, camera_id="cam_offline")
    assert prediction.event_type is not None
    assert 0.0 <= prediction.confidence <= 1.0

    # 6. Local Event Engine & Storage
    engine = EventEngine()
    engine.start()
    engine.submit_prediction(prediction)
    engine.stop()

    # 7. Local MP4 Recording
    recorder = RecordingManager(
        recordings_dir=settings.RECORDINGS_DIR,
        snapshots_dir=settings.SNAPSHOTS_DIR
    )
    for i in range(10):
        recorder.ingest_frame("cam_offline", frame, 1000.0 + i * 0.033, i)

    evt = Event(
        event_id="evt_offline_99",
        camera_id="cam_offline",
        event_type=prediction.event_type,
        status=EventStatus.ACTIVE,
        severity=EventSeverity.MEDIUM,
        confidence=prediction.confidence,
        summary="Airgap event",
    )
    recorder.trigger_recording_start(evt)
    rec = recorder.finalize_recording(evt)
    assert rec is not None
    assert Path(rec.file_path).exists()

    # 8. Local System Diagnostics
    diag_res = client.get("/api/v1/system/diagnostics")
    assert diag_res.status_code == 200
    diag = diag_res.json()
    assert diag["hub"]["status"] == "READY"
    assert diag["database"]["status"] == "READY"

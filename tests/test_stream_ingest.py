"""
Integration Tests for Stream Ingestion, Decoders & CameraSource Abstraction
Tests SS-DOC-005, SS-DOC-002, and ADR-006 compliance
"""

import pytest
import numpy as np
from services.stream_engine.protocol import (
    encode_packet,
    FRAME_TYPE_IDR,
    FRAME_TYPE_P
)
from services.stream_engine.server import stream_engine, PhoneCameraSource
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    settings.DATABASE_PATH = tmp_path / "test_stream_db.db"
    init_database()
    yield


def test_stream_session_packet_processing_and_gap_detection():
    camera_id = "cam_test_stream_01"
    session = stream_engine.get_or_create_session(camera_id)
    
    # 1. Feed packet sequence 0
    p0 = encode_packet(FRAME_TYPE_IDR, 0, 1000, b"\x00\x00\x00\x01\x67test_sps")
    stream_engine.process_binary_chunk(camera_id, p0)
    assert session.frames_received == 1
    assert session.dropped_packets == 0
    assert session.last_sequence == 0

    # 2. Feed packet sequence 3 (simulating lost packets 1 and 2)
    p3 = encode_packet(FRAME_TYPE_P, 3, 4000, b"\x00\x00\x00\x01\x41test_p")
    stream_engine.process_binary_chunk(camera_id, p3)
    assert session.frames_received == 2
    assert session.dropped_packets == 2  # Detected 2 dropped packets!
    assert session.last_sequence == 3

    metrics = session.get_metrics()
    assert metrics["camera_id"] == camera_id
    assert metrics["dropped_packets"] == 2
    assert metrics["frames_received"] == 2


def test_phone_camera_source_contract_compliance():
    """Validates that PhoneCameraSource correctly satisfies CameraSource interface."""
    import asyncio
    
    async def _test_coroutine():
        camera_id = "cam_contract_test"
        device_id = "dev_phone_contract"
        
        source = PhoneCameraSource(camera_id=camera_id, device_id=device_id)
        
        # Connect
        connected = await source.connect()
        assert connected is True
        
        # Capabilities
        caps = source.get_capabilities()
        assert (1280, 720) in caps.supported_resolutions
        assert 30 in caps.supported_fps
        assert caps.hardware_h264_decode is True
        
        # Start stream
        started = await source.start_stream()
        assert started is True
        
        # Status
        status = source.get_status()
        assert status["camera_id"] == camera_id
        
        # Disconnect
        await source.disconnect()

    asyncio.run(_test_coroutine())

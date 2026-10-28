"""
Smart Spectator - Real H.264 Media Ingestion & Decoding Integration Tests
Verifies real H.264 Annex-B stream generation, SSP1 packet framing,
PyAV hardware/software decoding, keyframe gating, error resilience, and AI pipeline handoff.
"""

import time
import pytest
import numpy as np
from fractions import Fraction
import av

from services.stream_engine.protocol import (
    encode_packet,
    decode_header,
    FRAME_TYPE_IDR,
    FRAME_TYPE_P,
    ProtocolError
)
from services.stream_engine.decoder import H264Decoder, is_keyframe_nal
from services.stream_engine.server import StreamEngine
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    # Stream sessions touch the cameras table; don't rely on a local smart_spectator.db
    orig = settings.DATABASE_PATH
    settings.DATABASE_PATH = tmp_path / "test_h264.db"
    init_database()
    yield
    settings.DATABASE_PATH = orig


def generate_h264_stream(num_frames: int = 10, width: int = 640, height: int = 480):
    """Generates real H.264 encoded packets using PyAV libx264 encoder."""
    enc = av.CodecContext.create("libx264", "w")
    enc.width = width
    enc.height = height
    enc.pix_fmt = "yuv420p"
    enc.time_base = Fraction(1, 30)
    enc.gop_size = 5  # Keyframe every 5 frames

    packets = []
    for i in range(num_frames):
        # Create a synthetic frame with varying content
        arr = np.zeros((height, width, 3), dtype=np.uint8)
        arr[:, :, 0] = (i * 25) % 256
        arr[50:150, 50:150, 1] = 255
        
        frame = av.VideoFrame.from_ndarray(arr, format="bgr24")
        frame.pts = i
        encoded = enc.encode(frame)
        for pkt in encoded:
            packets.append(pkt)

    flushed = enc.encode(None)
    for pkt in flushed:
        packets.append(pkt)

    return packets


def test_real_h264_encoding_and_decoding():
    """Verifies that real H.264 packets decode to valid NumPy image arrays."""
    packets = generate_h264_stream(num_frames=8)
    assert len(packets) > 0, "Failed to generate H.264 packets"

    decoder = H264Decoder()
    assert decoder.initialized, "PyAV H264Decoder failed to initialize"

    decoded_total = 0
    for pkt in packets:
        raw_bytes = bytes(pkt)
        is_kf = pkt.is_keyframe or is_keyframe_nal(raw_bytes)
        frames = decoder.decode_packet(raw_bytes, is_keyframe=is_kf)
        for f in frames:
            assert isinstance(f, np.ndarray)
            assert f.shape == (480, 640, 3)
            assert f.dtype == np.uint8
            decoded_total += 1

    assert decoded_total >= 5, f"Expected at least 5 decoded frames, got {decoded_total}"
    metrics = decoder.get_metrics()
    assert metrics["frames_decoded"] == decoded_total
    assert metrics["keyframe_count"] >= 1
    assert metrics["decode_errors"] == 0


def test_keyframe_gating_discards_early_p_frames():
    """Verifies that P-frames arriving before the initial keyframe are safely discarded."""
    packets = generate_h264_stream(num_frames=12)
    
    # Separate keyframe packets from subsequent P-frame packets
    keyframe_pkt = None
    p_frame_pkt = None
    for pkt in packets:
        if pkt.is_keyframe and keyframe_pkt is None:
            keyframe_pkt = pkt
        elif not pkt.is_keyframe and p_frame_pkt is None:
            p_frame_pkt = pkt

    assert keyframe_pkt is not None
    assert p_frame_pkt is not None

    decoder = H264Decoder()
    assert not decoder.has_received_keyframe

    # 1. Send P-frame first -> must be discarded
    dropped_frames = decoder.decode_packet(bytes(p_frame_pkt), is_keyframe=False)
    assert len(dropped_frames) == 0
    assert not decoder.has_received_keyframe
    assert decoder.packets_dropped_before_keyframe == 1

    # 2. Send keyframe -> must unlock the decoder
    kf_frames = decoder.decode_packet(bytes(keyframe_pkt), is_keyframe=True)
    assert decoder.has_received_keyframe
    assert decoder.keyframe_count == 1
    assert decoder.packets_dropped_before_keyframe == 1


def test_stream_engine_end_to_end_ssp1_pipeline():
    """Verifies full end-to-end flow: H.264 -> SSP1 framing -> StreamEngine chunk processing -> Decoded frame."""
    engine = StreamEngine()
    camera_id = "test_e2e_cam_01"

    packets = generate_h264_stream(num_frames=10)
    assert len(packets) > 0

    seq = 0
    now_us = int(time.time() * 1000000)

    for pkt in packets:
        frame_type = FRAME_TYPE_IDR if pkt.is_keyframe else FRAME_TYPE_P
        wire_packet = encode_packet(
            frame_type=frame_type,
            sequence_number=seq,
            pts_us=now_us + (seq * 33333),
            payload=bytes(pkt)
        )
        seq += 1

        engine.process_binary_chunk(camera_id, wire_packet)

    session = engine.sessions.get(camera_id)
    assert session is not None
    assert session.frames_received == len(packets)
    assert session.latest_frame is not None
    assert isinstance(session.latest_frame, np.ndarray)
    assert session.latest_frame.shape == (480, 640, 3)

    metrics = session.get_metrics()
    assert metrics["camera_id"] == camera_id
    assert metrics["has_decoded_frame"] is True
    assert metrics["frames_decoded"] > 0
    assert metrics["keyframe_count"] >= 1

    # Verify JPEG snapshot generation from the decoded frame
    jpeg_bytes = engine.get_latest_jpeg(camera_id, with_ai_overlay=False)
    assert jpeg_bytes is not None
    assert len(jpeg_bytes) > 100
    assert jpeg_bytes[:2] == b"\xff\xd8"  # JPEG Magic Bytes SOI

    engine.remove_session(camera_id)
    assert camera_id not in engine.sessions


def test_corrupted_packets_rejected_gracefully():
    """Verifies that corrupted packet payloads or truncated headers fail closed without crashing."""
    engine = StreamEngine()
    camera_id = "test_corrupt_cam"

    # 1. Truncated header (< 24 bytes)
    res = engine.process_binary_chunk(camera_id, b"\x53\x53\x01")
    assert res is None

    # 2. Corrupted CRC16
    valid_packet = bytearray(encode_packet(
        frame_type=FRAME_TYPE_IDR,
        sequence_number=1,
        pts_us=1000,
        payload=b"\x00\x00\x00\x01\x65\x88\x84\x00"
    ))
    # Flip bytes in CRC field (bytes 22, 23)
    valid_packet[22] ^= 0xFF
    res = engine.process_binary_chunk(camera_id, bytes(valid_packet))
    assert res is None

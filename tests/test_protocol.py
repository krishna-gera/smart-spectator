"""
Unit Tests for Smart Spectator 24-Byte Camera Binary Protocol
Tests SS-DOC-005 compliance
"""

import pytest
from services.stream_engine.protocol import (
    MAGIC_BYTES,
    PROTOCOL_VERSION,
    HEADER_SIZE_BYTES,
    FRAME_TYPE_IDR,
    FRAME_TYPE_P,
    FRAME_TYPE_AUDIO,
    encode_packet,
    decode_header,
    compute_crc16,
    ProtocolError
)


def test_valid_idr_packet_encoding_and_decoding():
    payload = b"\x00\x00\x00\x01\x67\x42\x00\x1f" # Mock SPS NAL
    seq = 42
    pts = 1727608800000000 # microseconds
    
    packet_bytes = encode_packet(
        frame_type=FRAME_TYPE_IDR,
        sequence_number=seq,
        pts_us=pts,
        payload=payload
    )
    
    assert len(packet_bytes) == HEADER_SIZE_BYTES + len(payload)
    
    header = decode_header(packet_bytes[:HEADER_SIZE_BYTES])
    assert header.magic == MAGIC_BYTES
    assert header.version == PROTOCOL_VERSION
    assert header.frame_type == FRAME_TYPE_IDR
    assert header.is_keyframe is True
    assert header.sequence_number == seq
    assert header.pts_us == pts
    assert header.payload_length == len(payload)
    
    # Check payload integrity
    extracted_payload = packet_bytes[HEADER_SIZE_BYTES:]
    assert extracted_payload == payload


def test_truncated_header_raises_protocol_error():
    short_header = b"\x53\x53\x01\x01" # Only 4 bytes
    with pytest.raises(ProtocolError, match="Header too short"):
        decode_header(short_header)


def test_invalid_magic_bytes_rejected():
    payload = b"test"
    valid_packet = encode_packet(FRAME_TYPE_P, 1, 1000, payload)
    
    # Corrupt magic byte (first byte)
    corrupted = bytearray(valid_packet)
    corrupted[0] = 0xFF
    
    with pytest.raises(ProtocolError, match="Invalid magic bytes"):
        decode_header(bytes(corrupted[:HEADER_SIZE_BYTES]))


def test_invalid_version_rejected():
    payload = b"test"
    valid_packet = encode_packet(FRAME_TYPE_P, 1, 1000, payload)
    
    # Corrupt version byte (byte 2)
    corrupted = bytearray(valid_packet)
    corrupted[2] = 0x02 # Version 2 unsupported
    
    with pytest.raises(ProtocolError):
        decode_header(bytes(corrupted[:HEADER_SIZE_BYTES]))


def test_corrupted_checksum_rejected():
    payload = b"test"
    valid_packet = encode_packet(FRAME_TYPE_P, 1, 1000, payload)
    
    # Tamper with sequence number inside header without updating CRC
    corrupted = bytearray(valid_packet)
    corrupted[4] ^= 0xFF
    
    with pytest.raises(ProtocolError, match="CRC16 checksum mismatch"):
        decode_header(bytes(corrupted[:HEADER_SIZE_BYTES]))


def test_oversized_payload_safety_cap():
    # Construct a header with payload length claiming 15MB
    import struct
    fake_header_pre = struct.pack(
        ">H B B I Q I H",
        MAGIC_BYTES,
        PROTOCOL_VERSION,
        FRAME_TYPE_P,
        1,
        1000,
        15 * 1024 * 1024, # 15MB (exceeds 10MB limit)
        0
    )
    crc = compute_crc16(fake_header_pre)
    fake_header = fake_header_pre + struct.pack(">H", crc)
    
    with pytest.raises(ProtocolError, match="Oversized payload length rejected"):
        decode_header(fake_header)

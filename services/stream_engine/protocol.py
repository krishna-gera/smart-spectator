"""
Smart Spectator - 24-Byte Binary Framing Protocol Parser & Serializer
Strictly implements docs/05_CAMERA_PROTOCOL.md
"""

import struct
from dataclasses import dataclass
from typing import Tuple, Optional

# Protocol Constants
MAGIC_BYTES = 0x5353       # 'SS'
PROTOCOL_VERSION = 0x01
HEADER_SIZE_BYTES = 24

# Frame Types
FRAME_TYPE_IDR = 0x01      # Instantaneous Decoder Refresh (Keyframe with SPS/PPS)
FRAME_TYPE_P = 0x02        # Predicted frame
FRAME_TYPE_B = 0x03        # Bidirectional predicted frame
FRAME_TYPE_AUDIO = 0x04    # Audio frame


def compute_crc16(data: bytes) -> int:
    """Computes CRC-16-CCITT (Poly: 0x1021, Init: 0xFFFF) over byte buffer."""
    crc = 0xFFFF
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


@dataclass
class PacketHeader:
    magic: int
    version: int
    frame_type: int
    sequence_number: int
    pts_us: int
    payload_length: int
    reserved: int
    crc16: int

    @property
    def is_keyframe(self) -> bool:
        return self.frame_type == FRAME_TYPE_IDR


class ProtocolError(Exception):
    """Raised when incoming video packet violates protocol invariants."""
    pass


def encode_packet(
    frame_type: int,
    sequence_number: int,
    pts_us: int,
    payload: bytes
) -> bytes:
    """
    Serializes an H.264 NAL unit into a Smart Spectator binary packet.
    Layout (24-byte header + payload):
      - uint16 magic (0x5353)
      - uint8  version (0x01)
      - uint8  frame_type
      - uint32 sequence_number
      - uint64 pts_us
      - uint32 payload_length
      - uint16 reserved (0x0000)
      - uint16 crc16 (computed over first 22 bytes)
    """
    payload_len = len(payload)
    reserved = 0x0000
    
    # Pack first 22 bytes to compute checksum
    header_pre = struct.pack(
        ">H B B I Q I H",
        MAGIC_BYTES,
        PROTOCOL_VERSION,
        frame_type,
        sequence_number,
        pts_us,
        payload_len,
        reserved
    )
    
    crc16 = compute_crc16(header_pre)
    full_header = header_pre + struct.pack(">H", crc16)
    
    return full_header + payload


def decode_header(header_bytes: bytes) -> PacketHeader:
    """
    Parses and validates 24-byte packet header.
    Raises ProtocolError if magic, version, or CRC16 are invalid.
    """
    if len(header_bytes) < HEADER_SIZE_BYTES:
        raise ProtocolError(f"Header too short: expected {HEADER_SIZE_BYTES} bytes, got {len(header_bytes)}")
        
    magic, version, frame_type, seq, pts, payload_len, reserved, crc16 = struct.unpack(
        ">H B B I Q I H H",
        header_bytes[:HEADER_SIZE_BYTES]
    )
    
    if magic != MAGIC_BYTES:
        raise ProtocolError(f"Invalid magic bytes: 0x{magic:04X} (expected 0x{MAGIC_BYTES:04X})")
        
    if version != PROTOCOL_VERSION:
        raise ProtocolError(f"Unsupported protocol version: {version} (expected {PROTOCOL_VERSION})")
        
    expected_crc = compute_crc16(header_bytes[:22])
    if crc16 != expected_crc:
        raise ProtocolError(f"CRC16 checksum mismatch: got 0x{crc16:04X}, expected 0x{expected_crc:04X}")
        
    # Safety sanity check on payload length (max 10MB per frame to prevent memory exhaustion)
    if payload_len > 10 * 1024 * 1024:
        raise ProtocolError(f"Oversized payload length rejected: {payload_len} bytes")
        
    return PacketHeader(
        magic=magic,
        version=version,
        frame_type=frame_type,
        sequence_number=seq,
        pts_us=pts,
        payload_length=payload_len,
        reserved=reserved,
        crc16=crc16
    )

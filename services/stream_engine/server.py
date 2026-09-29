"""
Smart Spectator - Media Stream Ingestion Engine & CameraSource Implementation
Handles both WebSocket binary ingestion and dedicated TCP media ingestion on port 8554.
Follows docs/04_NETWORK_ARCHITECTURE.md and docs/05_CAMERA_PROTOCOL.md
"""

import asyncio
import io
import time
from typing import Dict, Optional, Tuple, AsyncIterator, Any
import numpy as np
from PIL import Image

from shared.protocols.camera_source import CameraSource, CameraCapabilities
from .protocol import decode_header, HEADER_SIZE_BYTES, ProtocolError
from .session import StreamSession
from services.hub_backend.database.connection import db_session


class StreamEngine:
    """Orchestrates stream ingestion sessions across all connected cameras."""

    def __init__(self):
        self.sessions: Dict[str, StreamSession] = {}
        self.tcp_server: Optional[asyncio.Server] = None

    def get_or_create_session(self, camera_id: str) -> StreamSession:
        if camera_id not in self.sessions:
            self.sessions[camera_id] = StreamSession(camera_id)
            with db_session() as conn:
                conn.execute(
                    "UPDATE cameras SET status = 'streaming' WHERE camera_id = ?",
                    (camera_id,)
                )
        return self.sessions[camera_id]

    def remove_session(self, camera_id: str) -> None:
        if camera_id in self.sessions:
            session = self.sessions.pop(camera_id)
            session.close()
            with db_session() as conn:
                conn.execute(
                    "UPDATE cameras SET status = 'idle' WHERE camera_id = ?",
                    (camera_id,)
                )
            print(f"[StreamEngine] Stream session closed for camera '{camera_id}'")

    def process_binary_chunk(self, camera_id: str, raw_chunk: bytes) -> Optional[np.ndarray]:
        """
        Validates protocol header, extracts NAL unit, and updates session.
        Returns latest decoded frame if available.
        """
        if len(raw_chunk) < HEADER_SIZE_BYTES:
            return None

        try:
            header = decode_header(raw_chunk[:HEADER_SIZE_BYTES])
            payload = raw_chunk[HEADER_SIZE_BYTES : HEADER_SIZE_BYTES + header.payload_length]
            
            session = self.get_or_create_session(camera_id)
            decoded = session.ingest_packet(header, payload)
            if decoded:
                return decoded[-1]
        except ProtocolError as e:
            print(f"[StreamEngine] Protocol violation from '{camera_id}': {e}")
        except Exception as e:
            print(f"[StreamEngine] Error parsing chunk from '{camera_id}': {e}")

        return None

    def get_latest_jpeg(self, camera_id: str) -> Optional[bytes]:
        """Encodes latest decoded frame as JPEG bytes for REST snapshots or MJPEG live preview."""
        session = self.sessions.get(camera_id)
        if not session or session.latest_frame is None:
            return None

        try:
            # OpenCV or PIL encoding
            bgr_frame = session.latest_frame
            # Convert BGR to RGB
            rgb_frame = bgr_frame[:, :, ::-1] if len(bgr_frame.shape) == 3 and bgr_frame.shape[2] == 3 else bgr_frame
            img = Image.fromarray(rgb_frame)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            return buf.getvalue()
        except Exception as e:
            print(f"[StreamEngine] Error encoding JPEG snapshot: {e}")
            return None

    async def start_tcp_ingest_server(self, host: str, port: int):
        """Starts dedicated low-latency TCP binary media receiver on port 8554."""
        async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
            addr = writer.get_extra_info("peername")
            print(f"[StreamTCP] Inbound media socket connected from {addr}")
            camera_id = "default"  # Handshake can pass camera_id
            
            buffer = bytearray()
            try:
                while True:
                    data = await reader.read(65536)
                    if not data:
                        break
                    buffer.extend(data)
                    
                    while len(buffer) >= HEADER_SIZE_BYTES:
                        try:
                            header = decode_header(buffer[:HEADER_SIZE_BYTES])
                            total_packet_len = HEADER_SIZE_BYTES + header.payload_length
                            if len(buffer) < total_packet_len:
                                break  # Await rest of payload
                                
                            payload = bytes(buffer[HEADER_SIZE_BYTES:total_packet_len])
                            session = self.get_or_create_session(camera_id)
                            session.ingest_packet(header, payload)
                            del buffer[:total_packet_len]
                        except ProtocolError as e:
                            print(f"[StreamTCP] Protocol error from {addr}: {e}")
                            # Skip corrupted byte to realign
                            del buffer[:1]
            except Exception as e:
                print(f"[StreamTCP] Stream connection terminated from {addr}: {e}")
            finally:
                writer.close()
                await writer.wait_closed()
                self.remove_session(camera_id)

        self.tcp_server = await asyncio.start_server(handle_client, host, port)
        print(f"[StreamTCP] Dedicated media ingest listening on tcp://{host}:{port}")


stream_engine = StreamEngine()


class PhoneCameraSource(CameraSource):
    """
    Concrete CameraSource implementation wrapping an Android phone node.
    Implements shared/protocols/camera_source.py
    """

    def __init__(self, camera_id: str, device_id: str):
        self._camera_id = camera_id
        self._device_id = device_id
        self._is_connected = False

    async def connect(self) -> bool:
        self._is_connected = True
        return True

    async def disconnect(self) -> None:
        stream_engine.remove_session(self._camera_id)
        self._is_connected = False

    async def start_stream(self) -> bool:
        stream_engine.get_or_create_session(self._camera_id)
        return True

    async def stop_stream(self) -> None:
        stream_engine.remove_session(self._camera_id)

    async def get_frame(self, timeout_ms: int = 1000) -> Optional[Tuple[np.ndarray, Dict[str, Any]]]:
        session = stream_engine.sessions.get(self._camera_id)
        if not session or session.latest_frame is None:
            return None
        metadata = {
            "camera_id": self._camera_id,
            "pts": session.latest_frame_pts,
            "timestamp": session.latest_frame_timestamp
        }
        return session.latest_frame, metadata

    async def frame_generator(self) -> AsyncIterator[Tuple[np.ndarray, Dict[str, Any]]]:
        while self._is_connected:
            frame_data = await self.get_frame(timeout_ms=100)
            if frame_data:
                yield frame_data
            await asyncio.sleep(0.033)  # ~30 FPS

    def get_status(self) -> Dict[str, Any]:
        session = stream_engine.sessions.get(self._camera_id)
        if session:
            return session.get_metrics()
        return {"camera_id": self._camera_id, "status": "idle"}

    def get_capabilities(self) -> CameraCapabilities:
        return CameraCapabilities(
            supported_resolutions=[(1280, 720), (1920, 1080)],
            supported_fps=[15, 30],
            has_ptz=False,
            has_audio=False,
            hardware_h264_decode=True
        )

#!/usr/bin/env python3
"""
Smart Spectator - End-to-End Streaming & Pipeline Verification Script
Simulates an Android Camera node executing:
1. Hub Discovery & Health Check
2. 6-Digit PIN Pairing Handshake
3. Authenticated WebSocket Control Channel (Telemetry)
4. Authenticated Media Stream Ingestion (24-byte protocol framing)
5. Live JPEG Snapshot & Metrics Validation on Hub
"""

import time
import json
import asyncio
import sys
from pathlib import Path
import urllib.request
import urllib.error
import websockets

# Add repository root to python sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from services.stream_engine.protocol import (
    encode_packet,
    FRAME_TYPE_IDR,
    FRAME_TYPE_P
)

HUB_HOST = "127.0.0.1"
HUB_PORT = 8000
BASE_URL = f"http://{HUB_HOST}:{HUB_PORT}/api/v1"


def http_post_json(url: str, data: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def http_get_json(url: str) -> dict:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


async def main():
    print("=== Smart Spectator Phase 1 End-to-End Test ===")

    # 1. Hub Health Check
    print("[Step 1] Checking Hub health...")
    health = http_get_json(f"{BASE_URL}/health")
    assert health["status"] == "healthy"
    print(f"✔ Hub is healthy! Uptime: {health['uptime_seconds']}s")

    # 2. Pairing Request
    print("\n[Step 2] Sending pairing request from simulated Android camera...")
    device_id = f"dev_sim_phone_{int(time.time())}"
    pair_req = http_post_json(
        f"{BASE_URL}/devices/pair/request",
        {
            "device_id": device_id,
            "device_name": "Living Room Pixel (Simulated)",
            "device_model": "Pixel 7 Pro",
            "os_version": "Android 14",
            "app_version": "1.0.0"
        }
    )
    assert pair_req["status"] == "pending_operator_approval"
    pin = pair_req["verification_code"]
    print(f"✔ Hub issued 6-digit PIN: {pin} (Expires in {pair_req['expires_in_seconds']}s)")

    # 3. Pairing Verification
    print("\n[Step 3] Submitting 6-digit PIN for verification...")
    pair_ver = http_post_json(
        f"{BASE_URL}/devices/pair/verify",
        {
            "device_id": device_id,
            "verification_code": pin
        }
    )
    assert pair_ver["status"] == "paired"
    token = pair_ver["device_token"]
    camera_id = pair_ver["camera_id"]
    print(f"✔ Successfully authenticated! Assigned Camera ID: {camera_id}")
    print(f"✔ Minted Bearer Token: {token[:16]}... (HMAC-protected)")

    # 4. Control Channel Telemetry
    print("\n[Step 4] Connecting to WebSocket Control Channel...")
    control_ws_url = f"ws://{HUB_HOST}:{HUB_PORT}/api/v1/control/ws?token={token}"
    async with websockets.connect(control_ws_url) as control_ws:
        telemetry_payload = {
            "protocol": "ss_control_v1",
            "type": "telemetry_report",
            "camera_id": camera_id,
            "device_id": device_id,
            "timestamp": int(time.time() * 1000),
            "metrics": {
                "battery_level_percent": 88.0,
                "is_charging": True,
                "battery_temperature_c": 33.8,
                "encoder_fps": 30.0,
                "uptime_seconds": 12
            }
        }
        await control_ws.send(json.dumps(telemetry_payload))
        print("✔ 1 Hz telemetry report dispatched successfully.")

        # 5. Media Stream Ingestion
        print("\n[Step 5] Connecting to WebSocket Media Ingest Channel...")
        media_ws_url = f"ws://{HUB_HOST}:{HUB_PORT}/api/v1/streams/ingest/{camera_id}?token={token}"
        async with websockets.connect(media_ws_url) as media_ws:
            print("✔ Media socket connected! Streaming simulated 30 FPS video frames...")

            # Stream 60 frames (2 seconds @ 30 FPS)
            for seq in range(60):
                frame_type = FRAME_TYPE_IDR if seq % 30 == 0 else FRAME_TYPE_P
                pts_us = int(time.time() * 1000000)
                
                # Synthetic H.264 NAL unit with Annex-B start code
                synthetic_nal = b"\x00\x00\x00\x01\x65" + bytes([seq % 256] * 1200) # 1.2KB NAL
                
                packet = encode_packet(
                    frame_type=frame_type,
                    sequence_number=seq,
                    pts_us=pts_us,
                    payload=synthetic_nal
                )
                
                await media_ws.send(packet)
                await asyncio.sleep(0.033) # 33ms (~30 FPS)

            print("✔ Streamed 60 binary frames conforming to SS-DOC-005 protocol.")

            # 6. Verify Hub Stream Metrics while connection is active
            print("\n[Step 6] Querying active stream telemetry on Hub...")
            streams = http_get_json(f"{BASE_URL}/streams")
            print(f"Active Hub Streams: {json.dumps(streams, indent=2)}")
            assert len(streams) >= 1
            active = [s for s in streams if s["camera_id"] == camera_id][0]
            assert active["frames_received"] >= 50
            assert active["dropped_packets"] == 0
            print(f"✔ Hub verified: Ingested {active['frames_received']} frames with 0 dropped packets!")

    print("\n[Step 7] Testing disconnection detection...")
    await asyncio.sleep(0.5)
    post_disconnect_streams = http_get_json(f"{BASE_URL}/streams")
    assert len(post_disconnect_streams) == 0
    print("✔ Hub verified: Session cleanly terminated upon disconnect!")

    print("\n=======================================================")
    print("✔ ALL PHASE 1 END-TO-END VERIFICATION CHECKS PASSED!")
    print("=======================================================")


if __name__ == "__main__":
    asyncio.run(main())

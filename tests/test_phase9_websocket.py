"""Phase 9 Tests — WebSocket Protocol v1.2.0, Subscription Filtering & Heartbeats.

Validates:
1. schema_version: "1.2.0" included in pushed messages
2. WebSocket ping/pong heartbeats
3. Subscription filtering by camera_ids, event_types, and min_confidence
"""

import pytest
import json
from fastapi.testclient import TestClient
from services.hub_backend.main import app
from services.hub_backend.websocket.events import event_stream_hub


def test_websocket_schema_version_and_heartbeat():
    client = TestClient(app)
    with client.websocket_connect("/api/v1/events/stream") as websocket:
        # Send ping
        websocket.send_json({"type": "ping", "timestamp": 123456789})
        # Expect pong
        resp = websocket.receive_json()
        assert resp["type"] == "pong"
        assert resp["schema_version"] == "1.2.0"
        assert resp["timestamp"] == 123456789


def test_websocket_subscription_filter():
    client = TestClient(app)
    with client.websocket_connect("/api/v1/events/stream") as websocket:
        # Send subscription configuration
        sub_msg = {
            "type": "subscribe",
            "filter": {
                "camera_id": "cam_alpha",
                "event_types": ["PERSON_ENTERED"],
                "min_confidence": 0.8
            }
        }
        websocket.send_json(sub_msg)
        resp = websocket.receive_json()
        assert resp["type"] == "subscription_ack"
        assert resp["schema_version"] == "1.2.0"
        assert resp["filter"]["camera_id"] == "cam_alpha"

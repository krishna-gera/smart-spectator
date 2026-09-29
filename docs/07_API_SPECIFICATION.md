# Smart Spectator — REST & WebSocket API Specification

**Document ID:** `SS-DOC-007`  
**Phase:** Phase 0 (Architecture & Foundation)  
**Status:** Approved  
**Version:** OpenAPI 3.1 / Protocol v1  

---

## 1. Overview & Base URL

The Smart Spectator Desktop Hub exposes a unified local REST and WebSocket API.
- **Base HTTP URL:** `http://<hub-ip>:8000/api/v1`
- **Base WebSocket URL:** `ws://<hub-ip>:8000/api/v1`
- **Content Type:** `application/json` (REST) / `application/octet-stream` (Media Ingest)

---

## 2. Device Management Endpoints

### 2.1 Request Pairing
`POST /devices/pair/request`
- **Description:** Initiates pairing handshake for an unauthenticated camera node.
- **Request Body:**
  ```json
  {
    "device_id": "dev_android_9f81a7b4c2",
    "device_name": "Pixel 7 Node",
    "device_model": "Pixel 7 Pro",
    "os_version": "Android 14",
    "app_version": "1.0.0"
  }
  ```
- **Response (202 Accepted):**
  ```json
  {
    "status": "pending_operator_approval",
    "verification_code": "829410",
    "expires_in_seconds": 300
  }
  ```

### 2.2 Verify Pairing
`POST /devices/pair/verify`
- **Description:** Submits verification code to complete pairing and obtain credential.
- **Request Body:**
  ```json
  {
    "device_id": "dev_android_9f81a7b4c2",
    "verification_code": "829410"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "status": "paired",
    "camera_id": "cam_c109df82-41ba-4f81",
    "device_token": "ss_tok_v1_d389a1f46b87c4a10e74b391a82f3c09e81b2a4c6d",
    "token_type": "Bearer"
  }
  ```

### 2.3 List Devices
`GET /devices`
- **Response (200 OK):** Array of `Device` objects with connectivity, battery, and last-seen metrics.

### 2.4 Revoke Device
`DELETE /devices/{device_id}`
- **Response (200 OK):** `{ "status": "revoked", "device_id": "dev_android_9f81a7b4c2" }`

---

## 3. Camera & Stream Endpoints

### 3.1 List Cameras
`GET /cameras`
- **Response (200 OK):** Array of registered `Camera` objects.

### 3.2 Get Camera Details
`GET /cameras/{camera_id}`
- **Response (200 OK):** `Camera` object with current resolution, stream health, and lens status.

### 3.3 Start Camera Stream
`POST /cameras/{camera_id}/start`
- **Response (200 OK):** `{ "camera_id": "...", "status": "streaming" }`

### 3.4 Stop Camera Stream
`POST /cameras/{camera_id}/stop`
- **Response (200 OK):** `{ "camera_id": "...", "status": "stopped" }`

### 3.5 Fetch Latest Snapshot
`GET /cameras/{camera_id}/snapshot`
- **Response (200 OK):** `image/jpeg` payload of latest sampled frame.

---

## 4. Live Stream & Ingestion WebSockets

### 4.1 Camera Media Ingest (Node to Hub)
`WS /streams/ingest/{camera_id}`
- **Headers:** `Authorization: Bearer <token>`
- **Payload:** Binary H.264 stream with 24-byte protocol header (see `05_CAMERA_PROTOCOL.md`).

### 4.2 Client Live Stream (Hub to Web/Client)
`WS /streams/live/{camera_id}`
- **Payload:** Low-latency WebRTC / JSMpeg / fragmented MP4 payload for zero-lag browser canvas rendering.

---

## 5. Event & Monitoring Task Endpoints

### 5.1 Query Events
`GET /events?camera_id={id}&severity={sev}&limit=50&offset=0`
- **Response (200 OK):**
  ```json
  {
    "total": 142,
    "limit": 50,
    "offset": 0,
    "events": [
      {
        "event_id": "evt_7f18b39a",
        "camera_id": "cam_c109df82",
        "task_id": "tsk_mug_01",
        "event_type": "OBJECT_REMOVED",
        "severity": "medium",
        "confidence": 0.94,
        "summary": "Tracked bottle removed from Desk Zone",
        "timestamp": "2026-09-29T12:15:30Z",
        "recording_id": "rec_8b172a"
      }
    ]
  }
  ```

### 5.2 Real-time Event Broadcast
`WS /events/live`
- **Description:** Broadcasts JSON `Event` objects to all active client dashboards the instant an event is triggered.

### 5.3 List Monitoring Tasks
`GET /monitoring`
- **Response (200 OK):** Array of `MonitoringTask` objects.

### 5.4 Create Monitoring Task
`POST /monitoring`
- **Request Body:**
  ```json
  {
    "camera_id": "cam_c109df82",
    "name": "Watch Coffee Mug",
    "target_class": "bottle",
    "expected_state": "PRESENT",
    "trigger_condition": "DISAPPEARED_FOR_10S",
    "event_type": "OBJECT_REMOVED",
    "roi_polygon": [[0.2, 0.3], [0.8, 0.3], [0.8, 0.9], [0.2, 0.9]],
    "notification_policy": { "sound": true, "ui_banner": true }
  }
  ```
- **Response (201 Created):** Newly created `MonitoringTask` object with generated `task_id`.

### 5.5 Update / Delete Monitoring Task
- `PATCH /monitoring/{task_id}`: Activate, deactivate, or modify parameters.
- `DELETE /monitoring/{task_id}`: Remove task.

---

## 6. Recordings Endpoints

### 6.1 List Recordings
`GET /recordings?limit=30`
- **Response (200 OK):** List of historical event clips with metadata and duration.

### 6.2 Stream / Download Recording Clip
`GET /recordings/{recording_id}/stream`
- **Response (200 OK):** `video/mp4` with HTTP Range Header support for video seeking.

---

## 7. System Diagnostics & AI Status Endpoints

### 7.1 System Health
`GET /health`
- **Response (200 OK):**
  ```json
  {
    "status": "healthy",
    "uptime_seconds": 18240,
    "version": "1.0.0"
  }
  ```

### 7.2 Hub Resource Status
`GET /system/status`
- **Response (200 OK):** CPU %, RAM usage, SSD storage free/total, active camera count.

### 7.3 Snapdragon AI Engine Status
`GET /ai/status`
- **Response (200 OK):**
  ```json
  {
    "active_provider": "npu_qnn",
    "hardware_target": "Snapdragon X Elite Hexagon NPU",
    "npu_tops_rated": 45.0,
    "mean_detection_latency_ms": 5.8,
    "mean_tracking_latency_ms": 1.9,
    "mean_event_latency_ms": 7.4,
    "total_inference_fps": 20.0,
    "fallback_active": false
  }
  ```

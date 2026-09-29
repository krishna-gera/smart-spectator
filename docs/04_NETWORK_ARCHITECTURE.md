# Smart Spectator — Network Architecture

**Document ID:** `SS-DOC-004`  
**Phase:** Phase 0 (Architecture & Foundation)  
**Status:** Approved  

---

## 1. Network Topology & Environment

Smart Spectator operates natively within a **Standard Local Area Network (LAN)** (IPv4 / IPv6) established by residential or commercial Wi-Fi routers. The architecture is engineered to guarantee zero external cloud dependency, zero NAT-punching relay costs, and deterministic low latency across typical 2.4 GHz and 5 GHz wireless conditions.

```
+---------------------------------------------------------------------------------------+
|                                    LOCAL NETWORK (LAN)                                |
|                              Subnet: 192.168.1.0/24 (Example)                         |
+---------------------------------------------------------------------------------------+
                                           |
                    +----------------------+----------------------+
                    |                                             |
                    v                                             v
         +--------------------+                        +--------------------+
         |   Wi-Fi Router     |                        |  Ethernet Switch   |
         | (2.4 GHz / 5 GHz)  |                        |    (Optional)      |
         +---------+----------+                        +----------+---------+
                   |                                              |
      +------------+------------+                                 |
      |                         |                                 |
      v                         v                                 v
+--------------+         +--------------+              +--------------------+
| Phone Cam #1 |         | Phone Cam #2 |              |  Snapdragon Hub PC |
| (192.168.1.5)|         | (192.168.1.8)|              |   (192.168.1.10)   |
+--------------+         +--------------+              +--------------------+
                                                                  ^
                                                                  | Local Browser / Web
                                                       +----------+---------+
                                                       |  Monitoring Client |
                                                       |   (192.168.1.15)   |
                                                       +--------------------+
```

---

## 2. Dual-Channel Protocol Architecture

To prevent video frame serialization from blocking critical device control, keep-alive heartbeats, and alert dispatches, Smart Spectator strictly segregates communication into two distinct channels:

```
+--------------------+                                         +--------------------+
|                    |   Control Channel (Port 8000 /ws/control)   |                    |
|                    |========================================>|                    |
|    Camera Node     |   - JSON Telemetry & Diagnostics (1 Hz)  |    Desktop Hub     |
|   (Android Phone)  |   - Dynamic Bitrate & Resolution Cmds   |   (FastAPI Core)   |
|                    |<========================================|                    |
|                    |                                         |                    |
|                    |   Media Channel (Port 8554 /stream)     |                    |
|                    |---------------------------------------->|                    |
|                    |   - H.264 Annex-B Video Stream (30 FPS) |                    |
+--------------------+                                         +--------------------+
```

### 2.1 The Control Channel (Bi-directional WebSocket)
- **Port:** `8000` (`/api/v1/control/ws`)
- **Protocol:** WebSocket over TCP with TLS (or local WSS)
- **Data Format:** Versioned JSON messages
- **Traffic Direction:**
  - *Node $\to$ Hub:* Periodic telemetry packets (battery %, thermal reading, Wi-Fi RSSI, encoder dropped frames).
  - *Hub $\to$ Node:* Dynamic control commands (target resolution, frame rate cap, keyframe request `IDR`, torch/flash toggle).
- **Heartbeat & Liveness:** Ping/Pong frames every 3 seconds. Failure to respond within 9 seconds initiates reconnection handling.

### 2.2 The Media Channel (Unidirectional Binary Stream)
- **Port:** `8554` (`/api/v1/stream/ingest/{camera_id}`)
- **Protocol:** Low-latency H.264 Annex-B stream over TCP/WebSocket binary frames.
- **Data Payload:** Raw NAL units with 4-byte start codes (`0x00000001`), prefixed with a lightweight 16-byte binary header containing frame timestamp (`pts`), sequence index, and keyframe indicator flag.
- **Buffering Policy:** Non-blocking zero-copy ingestion buffer with dynamic packet dropping under high network jitter.

---

## 3. Discovery Protocol (mDNS / DNS-SD)

To achieve zero-configuration discovery without requiring manual IP address entry:

1. **Hub Broadcasting:** The Desktop Hub broadcasts an mDNS (Multicast DNS) service record on multicast address `224.0.0.251:5353`:
   - **Service Type:** `_smartspectator._tcp.local.`
   - **Instance Name:** `SmartSpectatorHub-<HOSTNAME>`
   - **TXT Records:**
     - `api_port=8000`
     - `stream_port=8554`
     - `version=1.0.0`
     - `hub_id=<UUID>`
     - `pairing_active=true/false`

2. **Node Resolution:** When launched, the Android camera app utilizes `android.net.nsd.NsdManager` to discover active hubs. Once discovered, the app extracts the Hub IP and initiates the pairing or authentication handshake.

3. **Fallback Mechanism:** If multicast is disabled on the router (e.g. client isolation active), the Android app provides an intuitive QR code scanner or manual IP entry prompt.

---

## 4. Connection Lifecycle & Reconnection State Machine

```
      +--------------+
      | DISCONNECTED |
      +-------+------+
              | (mDNS discovery or manual IP)
              v
       +--------------+
       |   PAIRING    |
       +-------+------+
              | (6-digit PIN confirmed)
              v
     +-----------------+
     |  AUTHENTICATED  |
     +--------+--------+
              | (Connect WS Control & Stream Sockets)
              v
     +-----------------+
     |    STREAMING    | <---------------+
     +--------+--------+                 |
              |                          |
    Network Disruption / Heartbeat Loss  | (Reconnection Success)
              |                          |
              v                          |
      +---------------+                  |
      | RECONNECTING  | -----------------+
      +-------+-------+
              | (Exponential Backoff: 1s, 2s, 4s, 8s, 16s, 30s)
              v (Max Retries Exceeded: 60s)
      +---------------+
      |  NODE OFFLINE |
      +---------------+
```

---

## 5. Bandwidth & Network Throughput Budgeting

Bandwidth requirements are optimized through H.264 constrained baseline profile encoding on Android hardware:

| Stream Configuration | Per-Camera Bitrate | 2 Cameras | 4 Cameras | Wi-Fi Bandwidth Utilization (100 Mbps LAN) |
| :--- | :--- | :--- | :--- | :--- |
| **720p @ 15 FPS** (Power Saver) | $1.0\text{ Mbps}$ | $2.0\text{ Mbps}$ | $4.0\text{ Mbps}$ | $4\%$ |
| **720p @ 30 FPS** (Default Balanced)| $2.5\text{ Mbps}$ | $5.0\text{ Mbps}$ | $10.0\text{ Mbps}$ | $10\%$ |
| **1080p @ 30 FPS** (High Quality)   | $4.5\text{ Mbps}$ | $9.0\text{ Mbps}$ | $18.0\text{ Mbps}$ | $18\%$ |

Even with 4 concurrent high-definition camera nodes streaming at 1080p, total network consumption remains under $20\text{ Mbps}$, well within the sustained throughput of standard 802.11ac/ax Wi-Fi networks.

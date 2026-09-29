# Security Hardening & Threat Model

This document outlines the security controls, authentication protocols, data privacy guarantees, and threat mitigations implemented across Smart Spectator.

---

## 1. Local-First Privacy Guarantee

Smart Spectator strictly operates within the boundaries of the user's Local Area Network (LAN):
- **Zero Cloud Ingress / Egress**: No telemetry, video streams, event frames, or inference embeddings are transmitted to third-party cloud services (AWS, GCP, Azure, Firebase, Supabase, or external LLM/VLM APIs).
- **On-Device Storage**: SQLite databases, recorded MP4 clips, and debug snapshots remain strictly on the host edge filesystem.
- **Offline Self-Sufficiency**: All ML models (YOLOv8n object detection, ByteTrack tracker, SpectatorNet temporal GRU) run locally on device hardware without requiring an internet connection.

---

## 2. Authentication & Session Security

### 2.1 Device Pairing Protocol
1. **PIN Generation**: The Hub generates a cryptographically random, 6-digit numeric PIN with a 5-minute expiry window.
2. **Device Handshake**: The Android device initiates pairing via `POST /devices/pair` transmitting:
   - `device_id`: Client UUID v4.
   - `pin`: Active 6-digit code.
   - `device_name`: Human-readable device label.
3. **Token Issuance**: The Hub authenticates the PIN and returns an opaque session token (`ss_tok_<uuid>`).
4. **Header-Based Auth**: Subsequent WebSocket and HTTP requests supply the token in HTTP headers:
   - `Authorization: Bearer <token>` or `X-Auth-Token: <token>`.
5. **Instant Revocation**: When an administrator revokes a camera device (`POST /devices/{id}/revoke`), the Hub immediately terminates any active camera video streaming WebSockets and invalidates the authentication token in SQLite.

---

## 3. Threat Mitigation Summary

| Threat Vector | Mitigation Strategy |
| :--- | :--- |
| **Token Exposure in Logs** | `SensitiveDataFilter` sanitizes logs via regex scrubbing of `ss_tok_*`, `Bearer *`, and 6-digit PIN patterns before writing to console or disk. |
| **Path Traversal Attack** | Strict canonical path validation in static and media routers preventing escape outside `recordings/`, `snapshots/`, and `backups/`. |
| **Denial of Service (Memory Exhaustion)** | Bounded ring buffers (`collections.deque(maxlen=90)`) for incoming video streams; oldest frames are dropped when queue saturates. |
| **Denial of Service (Disk Exhaustion)** | Pre-write disk space guard checking `MIN_FREE_DISK_MB` (500 MB). Video recording gracefully degrades if threshold is reached. |
| **Replay / Spoofing on LAN** | High-entropy random session tokens verified per request; device IDs strictly validated against UUID v4 formatting. |
| **Stale Device Persistence** | Explicit revocation API immediately shuts down open sockets and purges connection maps. |

---

## 4. Operational Best Practices

1. **Dedicated VLAN / Subnet**: For maximum physical security, place camera devices and the edge hub on an isolated IoT VLAN.
2. **Filesystem Permissions**: Run the Hub under a dedicated, unprivileged system user (`spectator`) with read-only access to system binaries and write access restricted to media and database directories.
3. **Database Encryption (Optional)**: If hardware theft is a concern, edge administrators can deploy SQLCipher or full-disk encryption (LUKS / BitLocker) on the host storage volume.

# Smart Spectator — Security Architecture & Threat Model

**Document ID:** `SS-DOC-013`  
**Phase:** Phase 0 (Architecture & Foundation)  
**Status:** Approved  

---

## 1. Security Architecture Principles

Smart Spectator is designed for **Local Zero-Trust Operation**. The system assumes that local Wi-Fi networks (especially shared residential or office networks) may contain untrusted, compromised, or curious endpoints.

Core security tenets:
1. **Explicit Consent & Physical Proximity:** No device can join the visual intelligence mesh without physical proximity verification (6-digit numeric exchange or QR scan) and explicit desktop approval.
2. **Strict Boundary Containment:** Private video streams, frames, embeddings, and recordings strictly never cross external gateway routers.
3. **Defense in Depth:** Rigorous binary header sanitization, bounded memory allocation in video buffers, and rate-limited API endpoints prevent Denial-of-Service and buffer overflow exploits.

---

## 2. Threat Modeling & Countermeasures Matrix

| Threat ID | Threat Vector | Risk Level | Architectural Countermeasure |
| :--- | :--- | :--- | :--- |
| **TH-01** | **Rogue Camera Ingestion:** Unauthorized device spoofing a phone node to inject fraudulent video. | **High** | Cryptographic bearer token authentication on media ingest socket; unauthenticated sockets dropped immediately before frame parsing. |
| **TH-02** | **Unauthorized Stream Eavesdropping:** Compromised LAN laptop snooping on video feeds. | **Critical** | Local TLS / WSS encryption for control and client streaming channels; session authentication required for all video routes. |
| **TH-03** | **Malformed Video Decoder Exploits:** Specially crafted H.264 NAL bytes attempting buffer overflow in FFmpeg/PyAV. | **High** | Pre-decoder binary sanity validation; 24-byte packet header CRC16 check; memory-bounded circular ring buffer allocations. |
| **TH-04** | **Replay Attacks:** Adversary capturing and re-transmitting valid historical packets. | **Medium** | Monotonically increasing sequence counters and timestamp window verification ($\pm 2.0\text{ seconds}$ delta check). |
| **TH-05** | **Control Channel Denial-of-Service:** Flooding WebSocket control channel with high-frequency JSON packets. | **Medium** | Token-bucket rate limiting ($5\text{ packets/sec}$ max per node); automatic socket disconnection on rate violation. |
| **TH-06** | **Credential Exposure on Device Theft:** Compromised phone providing access to Hub data. | **Medium** | Phone stores only an ingestion token with zero read privileges to other camera streams or database records; instant revocation from Hub dashboard. |

---

## 3. Cryptographic Specifications

- **Token Construction:** High-entropy 256-bit random secrets formatted as `ss_tok_v1_<hex_digest>`.
- **Database Storage:** Stored as `HMAC-SHA256` hashes in the SQLite `devices` table; raw tokens are never persisted in plaintext on the Hub.
- **Node Storage:** Stored in Android `EncryptedSharedPreferences` backed by the hardware **Android Keystore System** (hardware-backed TEE / StrongBox).
- **Transport Encryption:** Support for TLS 1.3 / WSS via self-signed local certificates auto-generated during Hub initialization.

---

## 4. Privacy & Compliance Guarantees

- **Zero Cloud Analytics:** The software contains zero third-party telemetry beacons (no Google Analytics, no Firebase, no Sentry).
- **Local Storage Ownership:** All SQLite records and MP4 event recordings reside entirely within the user's chosen local directory.
- **Immediate Data Wipe:** Complete system reset and data purge supported via single command or Hub settings UI.

---

## 5. Phase 6 Production Security Hardening

In Phase 6, additional defense-in-depth protections were implemented and verified:
1. **Automated Structured Log Scrubbing (`SensitiveDataFilter`)**:
   - Console and rotating file handlers scrub all bearer tokens, `ss_tok_*` strings, and 6-digit PIN patterns into `[REDACTED]`.
2. **Instant Active Stream Session Termination**:
   - Revoking a device via `POST /devices/{id}/revoke` immediately tears down and disconnects active camera streaming WebSockets.
3. **Storage Denial-of-Service Protection**:
   - `ClipRecorder` enforces a minimum free disk threshold (`MIN_FREE_DISK_MB = 500MB`). If storage drops below this, video encoding gracefully degrades to protect system files and database integrity.
4. **Header-Based Authentication**:
   - Camera media transport and client channels accept credentials via `Authorization: Bearer <token>` and `X-Auth-Token` to eliminate sensitive query parameter exposure in network proxies or browser histories.


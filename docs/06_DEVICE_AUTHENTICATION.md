# Smart Spectator — Device Authentication & Pairing Protocol

**Document ID:** `SS-DOC-006`  
**Phase:** Phase 0 (Architecture & Foundation)  
**Status:** Approved  

---

## 1. Authentication Philosophy

Smart Spectator operates on a **Local Zero-Trust Architecture**. Even though devices share a local Wi-Fi network, physical network access does not confer automatic surveillance stream access. 

Key principles:
1. **Explicit Operator Approval:** No camera node may stream frames to the Hub without explicit human approval at the Hub desktop.
2. **Cryptographic Device Credentials:** Once paired, nodes authenticate using cryptographically signed, pre-shared tokens with HMAC validation.
3. **Instant Device Revocation:** An operator can revoke any connected or paired phone instantly from the Hub dashboard.
4. **Resistant to Local Snooping:** Unauthenticated clients on the LAN cannot access live camera feeds or API endpoints.

---

## 2. Pairing Sequence Flow

The pairing sequence provides a secure, friction-free onboarding experience using a **6-Digit Secure Verification Code** or **QR Code**.

```
[ Android Camera Node ]                                       [ Desktop Hub ]
          |                                                          |
          | 1. mDNS Discovery / QR Scan                              |
          |    (Discovers Hub IP:Port and hub_id)                    |
          |                                                          |
          | 2. POST /api/v1/devices/pair/request                     |
          |    Body: { device_id, device_name, model, os }           |
          |--------------------------------------------------------->|
          |                                                          |
          |                                                          | 3. Hub Generates 6-Digit PIN
          |                                                          |    Displays on Desktop UI
          |                                                          |    Status: PENDING_APPROVAL
          |                                                          |
          | 4. Operator inputs PIN on phone OR approves on desktop   |
          |    POST /api/v1/devices/pair/verify                      |
          |    Body: { device_id, pin: "482910" }                    |
          |<-------------------------------------------------------->|
          |                                                          |
          |                                                          | 5. Hub Validates PIN
          |                                                          |    Generates HMAC Device Token
          |                                                          |    Stores in SQLite DB
          | 6. HTTP 200 OK                                           |
          |    Body: { status: "PAIRED", device_token: "..." }       |
          |<---------------------------------------------------------|
          |                                                          |
          | 7. Node stores token in Android EncryptedSharedPreferences
```

---

## 3. Pairing Payload Contracts

### 3.1 Initial Pairing Request (`POST /api/v1/devices/pair/request`)

```json
{
  "device_id": "dev_android_9f81a7b4c2",
  "device_name": "Living Room Pixel 7",
  "device_model": "Pixel 7 Pro",
  "os_version": "Android 14 (API 34)",
  "app_version": "1.0.0",
  "client_nonce": "9a38f71b29a8f4c1"
}
```

**Response (HTTP 202 Accepted):**
```json
{
  "status": "pending_operator_approval",
  "verification_code": "829410",
  "expires_in_seconds": 300,
  "hub_id": "hub_snapdragon_01"
}
```

### 3.2 Pair Verification (`POST /api/v1/devices/pair/verify`)

```json
{
  "device_id": "dev_android_9f81a7b4c2",
  "verification_code": "829410",
  "client_nonce": "9a38f71b29a8f4c1"
}
```

**Response (HTTP 200 OK):**
```json
{
  "status": "paired",
  "camera_id": "cam_c109df82-41ba-4f81",
  "device_token": "ss_tok_v1_d389a1f46b87c4a10e74b391a82f3c09e81b2a4c6d",
  "token_type": "Bearer",
  "expires_at": "2026-10-29T12:00:00Z"
}
```

---

## 4. Subsequent Stream & Control Authentication

Once paired, the camera node establishes connections without user intervention:

### 4.1 HTTP REST Requests
Node passes the token in the standard HTTP header:
```http
Authorization: Bearer ss_tok_v1_d389a1f46b87c4a10e74b391a82f3c09e81b2a4c6d
```

### 4.2 WebSocket Media & Control Connections
WebSocket connections pass the token as a subprotocol or query parameter upon connection handshake:
```
GET /api/v1/control/ws?token=ss_tok_v1_d389a1f46b87c4a10e74b391a82f3c09e81b2a4c6d HTTP/1.1
Host: 192.168.1.10:8000
Upgrade: websocket
Connection: Upgrade
```

The Hub validates:
1. Token format and prefix.
2. Token hash match against `devices.auth_token_hash` in SQLite.
3. Device status is not `REVOKED`.
4. Token expiration timestamp.

---

## 5. Token Revocation & Security Lifecycle

- **Revocation:** When an operator clicks "Revoke Device" on the Hub dashboard, the Hub sets `status = 'revoked'` in the database and terminates active WebSocket and media streaming sockets immediately with close code `4403 (Forbidden)`.
- **Token Rotation:** Devices can request token rotation every 30 days via `POST /api/v1/devices/token/refresh`.
- **Brute Force Protection:** The Hub locks pairing attempts after 3 incorrect verification codes for a duration of 10 minutes.

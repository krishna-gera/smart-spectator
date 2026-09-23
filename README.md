# Smart Spectator

<p align="center">
  <b>Turn any spare smartphone into an AI-powered visual observer & local server.</b>
</p>

---

## 🌟 The New Core Architecture: Local First

Smart Spectator transforms a spare smartphone into an authoritative embedded server:

- **THE CAMERA PHONE IS THE SERVER (`CAM CODER`)**:
  - Runs an embedded Dart HTTP & WebSocket server (`0.0.0.0:8080`) directly on Android and iOS.
  - Owns the local SQLite database (`sqflite`).
  - Executes local edge CV, adaptive sampling, and rule evaluation.
  - Generates monotonic event sequence numbers (`sequence_number`).
  - Stores evidence frames locally.
  - Advertises local Wi-Fi discovery (`_smart-spectator._tcp`).
  - Fully functional **offline** even without internet!
- **THE VIEWER PHONE IS THE CLIENT (`VIEW ACCESS`)**:
  - Discovers the CAM CODER on local Wi-Fi automatically.
  - Connects using a 3-tier priority hierarchy:
    1. **Local Wi-Fi**: Direct LAN HTTP/WS (`🟢 CONNECTED · LOCAL`)
    2. **Direct P2P**: WebRTC via STUN (`🟢 CONNECTED · P2P`)
    3. **Relay Fallback**: TURN relay (`🟡 CONNECTED · RELAY`)
  - Detects missing sequence numbers and performs automatic state reconciliation.
- **THE CLOUD IS STRICTLY OPTIONAL INFRASTRUCTURE**:
  - Provides WebRTC signaling (`/ws/signaling`).
  - Coordinates STUN/TURN traversal.
  - Relays push notifications (FCM).
  - Offers optional remote VLM inference if permitted.
  - **Never** stores camera video or acts as the authoritative state database.

---

## 🚀 Quickstart

### 1. Launch the CAM CODER (Camera Phone)
```bash
cd apps/mobile
flutter run
# Select "CAM CODER"
```
The camera view starts, the embedded server binds to port 8080, and the local database initializes. Tap **"Pair View"** to display the QR code and 8-character single-use code (`7F4K-92QM`).

### 2. Launch the VIEW ACCESS (Viewer Device)
```bash
# On a second phone, tablet, or simulator:
cd apps/mobile
flutter run
# Select "VIEW ACCESS" -> Scan the QR code or enter "7F4K-92QM"
```
The viewer connects directly over your local Wi-Fi network with `🟢 CONNECTED · LOCAL`.

### 3. Optional: Web Command Dashboard & Mobile PWA
```bash
# Desktop Command Center
cd apps/web-dashboard
npm run dev

# Mobile Web PWA
cd apps/web-mobile
npm run dev -- -p 3001
```

### 4. Optional: Cloud Signaling & Helper Infrastructure
```bash
docker compose up -d
```
FastAPI runs on `http://localhost:8000` providing WebRTC signaling and STUN traversal helpers.

---

## 🔒 Security & Privacy

- **On-Device Data Sovereignty**: All monitoring sessions, images, and events remain on the CAM CODER phone.
- **Cryptographic Device Identities**: Persistent keypairs stored securely in Keychain / Keystore.
- **Single-Use Expiring Codes**: Ephemeral 8-character codes (`7F4K-92QM`) expire after 5 minutes.
- **Revocation**: The CAM CODER can revoke any paired viewer instantly from settings.
- **Power Saver**: Built-in screen dimmer while continuous monitoring and serving continues.

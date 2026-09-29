# Smart Spectator — System Overview

**Document ID:** `SS-DOC-001`  
**Phase:** Phase 0 (Architecture & Foundation)  
**Target Platform:** Snapdragon-powered Windows/macOS PCs + Android Camera Nodes  
**Competition Context:** Snapdragon AI Lab Build & Present Challenge  

---

## 1. Executive Summary

**Smart Spectator** is a local-first, privacy-preserving visual intelligence ecosystem designed to transform ubiquitous, underutilized smartphones into high-definition intelligent camera nodes, orchestrated by a central **Snapdragon-powered Desktop Hub**. 

Traditional visual surveillance systems rely heavily on expensive CCTV hardware, proprietary NVRs (Network Video Recorders), and centralized cloud processing subscriptions. Cloud processing introduces prohibitive bandwidth requirements, high recurring costs, variable latency, and severe privacy vulnerabilities. Conversely, edge-only smart cameras struggle with thermal constraints, limited battery endurance, and insufficient compute capacity to execute multi-stage temporal reasoning.

Smart Spectator solves this dilemma through a **hybrid edge-hub computing topology**:
- **Camera Nodes (Android)** capture, hardware-encode, and transmit low-latency video over the local Wi-Fi network while remaining computationally lightweight, thermally stable, and energy-efficient.
- **Desktop Hub (Snapdragon PC)** acts as the local edge supercomputer: ingesting multiple camera streams, performing hardware-accelerated video decoding, running multi-tier AI perception and temporal reasoning via on-device NPU acceleration, evaluating monitoring policies, managing ring-buffered event recording, and hosting a local dashboard.
- **Client Interfaces (Web/Desktop)** provide immediate visual oversight, task configuration, real-time alerting, and historical event analysis without relying on external internet connectivity.

```
+-----------------------------------------------------------------------------------+
|                            SMART SPECTATOR ECOSYSTEM                              |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|   +-----------------------+              +------------------------------------+   |
|   |  Android Camera Node  |              |        Desktop Hub (Local PC)      |   |
|   |  - Flutter Camera UI  |              |  - Snapdragon Hexagon NPU          |   |
|   |  - H.264 HW Encoder   |              |  - Local FastAPI Orchestrator      |   |
|   |  - Local mDNS Beacon  |              |  - Multi-Camera Ring Buffer        |   |
|   |  - Battery/Thermal Tx |              |  - Event Engine & SQLite WAL       |   |
|   +-----------+-----------+              +-----------------+------------------+   |
|               |                                            |                      |
|               | Real-Time Stream (H.264/TCP)               | Local REST/WebSocket |
|               | Control & Telemetry (WS)                   | Dashboard & Video    |
|               v                                            v                      |
|       [ Local LAN Router ]                       +--------------------+           |
|       (Zero Cloud Relays)                        | Monitoring Client  |           |
|                                                  | Web / Mobile View  |           |
|                                                  +--------------------+           |
+-----------------------------------------------------------------------------------+
```

---

## 2. Core Value Proposition

1. **Repurposed Hardware Sustainability:** Turns existing Android smartphones into high-definition security and monitoring nodes without requiring proprietary IP cameras.
2. **Snapdragon Silicon Leadership:** Harnesses the 45+ TOPS Qualcomm Hexagon NPU on Snapdragon X-series platforms, offloading intensive visual perception from CPU/GPU and enabling continuous 24/7 multi-camera inference at ultra-low power envelopes.
3. **Local-First Privacy Guarantee:** Video streams, frame buffers, AI embeddings, telemetry, and event recordings never leave the local LAN boundary.
4. **Spatial-Temporal Intelligence:** Moves beyond simplistic object detection boxes to temporal event comprehension ("Object Removed", "Person Entered Zone", "Monitoring Task Completed", "Camera Obstructed") via our custom **SpectatorNet** event model.
5. **Universal Source Decoupling:** Employs an extensible `CameraSource` abstraction, enabling Phase 1 phone nodes to seamlessly coexist with future industrial RTSP, ONVIF, and USB camera streams.

---

## 3. Challenge Context & Evaluation Alignment

Smart Spectator is developed specifically for the **Snapdragon AI Lab Build & Present Challenge**, targeting Snapdragon-powered HP PCs. The architecture directly satisfies all primary evaluation criteria:

| Evaluation Area | Smart Spectator Architectural Focus |
| :--- | :--- |
| **Technical Implementation** | Modular monolith design; strict abstraction layers (`CameraSource`, `InferenceProvider`, `AIModel`); zero-copy frame pipeline; multi-threaded circular ring buffering; asynchronous FastAPI orchestration; SQLite WAL concurrency. |
| **Use Case & Innovation** | High-utility home/office automation and security; user-defined monitoring tasks (e.g. "Alert if my medication is removed", "Alert if front porch is blocked"); custom temporal neural network (SpectatorNet). |
| **Deployment & Accessibility** | Zero-friction local setup; mDNS zero-configuration discovery; 6-digit numeric pairing; self-contained local binaries on Windows and macOS. |
| **Presentation & Documentation** | Live telemetry streaming (NPU utilization, latency, FPS, thermal metrics); end-to-end trace logs; transparent evaluation benchmarks comparing NPU vs. GPU vs. CPU performance. |

---

## 4. System Boundaries & Guarantees

### What the System Guarantees:
- **Local Autonomy:** Complete functional operation without active WAN / Internet access.
- **Deterministic Latency:** Glass-to-screen and glass-to-alert latency under 250 milliseconds over standard 5 GHz Wi-Fi 6.
- **Fail-Safe Degradation:** Dynamic frame-rate shedding and provider fallback (NPU $\to$ GPU $\to$ CPU) if hardware limits are approached.
- **Storage Conservation:** Continuous rolling ring-buffer architecture with event-anchored persistence ($T - 15\text{s}$ pre-roll to $T + 15\text{s}$ post-roll), preventing disk exhaustion.

### Explicit Phase 0 Boundary:
- Phase 0 defines the complete technical specifications, mathematical protocols, interface contracts, and database schemas.
- Implementation of models, streaming engines, Flutter widgets, and network listeners begins in Phase 1 following this specification.

# Smart Spectator Compatibility Matrix

This document defines the certified hardware platforms, operating systems, and inference provider configurations for Smart Spectator.

---

## 1. Edge Hub Platform Compatibility

| Platform / SoC | Operating System | Preferred Execution Provider | Fallback Provider | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Qualcomm Snapdragon X Elite / Plus** | Windows on ARM (WoA) / Linux | `QNNExecutionProvider` (Hexagon NPU) | `DirectMLExecutionProvider` / `CPU` | Primary Target |
| **Qualcomm Snapdragon 8cx Gen 3** | Windows on ARM / Linux | `QNNExecutionProvider` | `CPUExecutionProvider` | Supported |
| **Qualcomm Snapdragon RB5 / RB3 Gen 2** | Ubuntu / Debian ARM64 | `QNNExecutionProvider` | `CPUExecutionProvider` | Supported |
| **Apple Silicon (M1/M2/M3/M4)** | macOS 12+ | `CoreMLExecutionProvider` | `CPUExecutionProvider` | Verified in CI/Dev |
| **Generic x86_64 (Intel / AMD)** | Linux / Windows | `OpenVINOExecutionProvider` / `CUDA` | `CPUExecutionProvider` (AVX2) | Supported |
| **Raspberry Pi 5 / RK3588** | Linux ARM64 | `CPUExecutionProvider` (NEON) | `CPUExecutionProvider` | Supported |

---

## 2. Camera Device Compatibility

| Device Tier | OS Version | Video Resolution | Transport | Performance Profile |
| :--- | :--- | :--- | :--- | :--- |
| **Flagship Android (Snapdragon 8 Gen 2/3)** | Android 13+ | 1280x720 @ 30 FPS | WebSocket Binary JPEG | Optimal (< 35ms latency) |
| **Mid-range Android (Snapdragon 7 / 6)** | Android 10+ | 1280x720 @ 25-30 FPS | WebSocket Binary JPEG | Standard (< 45ms latency) |
| **Entry / Legacy Android** | Android 9+ (API 28) | 640x480 @ 20-25 FPS | WebSocket Binary JPEG | Supported (< 60ms latency) |

---

## 3. Client Browser Compatibility

The web monitoring client is designed with zero external frontend dependencies (vanilla modern HTML5, ES Modules, CSS Custom Properties):
- **Google Chrome**: 90+ (Desktop & Mobile)
- **Mozilla Firefox**: 88+
- **Apple Safari**: 14+ (macOS & iOS)
- **Microsoft Edge**: 90+

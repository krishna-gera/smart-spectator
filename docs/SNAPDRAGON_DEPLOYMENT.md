# Qualcomm Snapdragon Deployment Guide

This guide details configuring and optimizing Smart Spectator on Qualcomm Snapdragon platforms, including Snapdragon X Elite/Plus laptops running Windows on ARM (WoA) and Qualcomm IoT Linux edge devices.

---

## 1. Supported Snapdragon Silicon

Smart Spectator is architected to leverage Qualcomm Hexagon NPU and Adreno GPU architectures:
- **Snapdragon X Elite / Snapdragon X Plus** (45 TOPS Hexagon NPU)
- **Snapdragon 8cx Gen 3 / Gen 2** (Computing platforms)
- **Snapdragon RB5 / RB3 Gen 2** (Robotics and Edge IoT platforms)

---

## 2. Software Stack & Drivers

### 2.1 Qualcomm Neural Processing SDK (QNN)
To utilize the Hexagon NPU directly:
1. Download Qualcomm AI Hub / Qualcomm Neural Processing SDK (v2.20+ recommended).
2. Install Qualcomm NPU drivers for your OS.
3. Install `onnxruntime-qnn` package:
   ```bash
   pip install onnxruntime-qnn
   ```
4. Verify driver installation by confirming that `QNNExecutionProvider` is registered:
   ```python
   import onnxruntime as ort
   print("Available providers:", ort.get_available_providers())
   ```

### 2.2 DirectML Acceleration (Windows on ARM)
On Windows on Snapdragon devices without direct QNN drivers installed:
```bash
pip install onnxruntime-directml
```
Smart Spectator will automatically prioritize `DirectMLExecutionProvider` to utilize the Adreno GPU and Hexagon NPU via Microsoft DirectML.

---

## 3. Deployment Configuration

### 3.1 Model Loading with Provider Fallback
Smart Spectator automatically executes the fallback chain via `InferenceProviderManager`:
```python
from ai.inference.manager import InferenceProviderManager

# Loads with optimal hardware provider: QNN -> DirectML -> CPU
session = InferenceProviderManager.load_model_with_fallback(
    "ai/models/releases/spectatornet_v1_int8.onnx",
    preferred_providers=["QNNExecutionProvider", "DirectMLExecutionProvider", "CPUExecutionProvider"]
)
```

### 3.2 Provider Options for QNN
When configuring QNN on Snapdragon:
```python
qnn_options = {
    "backend_path": "QnnHtp.dll",  # Hexagon Tensor Processor backend
    "htp_performance_mode": "burst", # High throughput mode
    "htp_precision": "quantized"      # For INT8 models
}
```

---

## 4. Hardware Verification & Reporting

Verify the active provider via the Hub API:
```bash
curl -s http://localhost:8000/system/hardware | jq .
```
Expected output on Snapdragon hardware:
```json
{
  "active_providers": ["QNNExecutionProvider"],
  "snapdragon_npu_detected": true,
  "cpu_threads": 12,
  "device_name": "Snapdragon(R) X Elite - X1E80100"
}
```
If deployed on non-Snapdragon hardware (e.g., macOS or generic x86_64), the API truthfully reports:
```json
{
  "active_providers": ["CoreMLExecutionProvider", "CPUExecutionProvider"],
  "snapdragon_npu_detected": false,
  "status_note": "Pending physical Snapdragon hardware / QNN SDK"
}
```

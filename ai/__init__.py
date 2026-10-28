"""Smart Spectator AI Package"""

import os

# See services/__init__.py: disable ONNX Runtime telemetry before onnxruntime is imported.
os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")

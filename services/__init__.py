"""Smart Spectator Services Package"""

import os

# ONNX Runtime ships Microsoft telemetry that uploads over HTTPS; disable it to keep the
# hub air-gapped and to avoid its exit-time teardown race (libc++abi recursive_mutex abort).
# Must be set before onnxruntime is first imported.
os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")

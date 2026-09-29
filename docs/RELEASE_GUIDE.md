# Smart Spectator Release Guide (Version 1.0.0)

This guide documents the release procedures, packaging, version validation, and checksum verification for Smart Spectator 1.0.0.

---

## 1. Release Manifest & Artifacts

All production model artifacts are organized under `ai/models/releases/` and tracked with SHA-256 hashes in `manifest.json`:

```json
{
  "version": "1.0.0",
  "generated_at": "2026-09-29T16:35:46.852784",
  "models": {
    "spectatornet_fp32": {
      "filename": "spectatornet_v1.onnx",
      "format": "ONNX",
      "sha256": "47228800f7e491c36087b32408018e69fa090b8f411aa6027a0808cf70ddcc0d",
      "input_shape": [1, 30, 166],
      "output_shape": [1, 5]
    },
    "spectatornet_int8": {
      "filename": "spectatornet_v1_int8.onnx",
      "format": "ONNX_INT8_QUANTIZED",
      "sha256": "c86eec085be9e7fec3bf310b8cf896791523ec3e33f3801ea8dc776100eb743c",
      "input_shape": [1, 30, 166],
      "output_shape": [1, 5]
    },
    "detector_fp32": {
      "filename": "detector_v1.onnx",
      "format": "ONNX",
      "sha256": "43916e788eb23528b746a583e78696ec09139268f76e3b2e7a177ff26e0eef2a",
      "input_shape": [1, 3, 640, 640]
    }
  }
}
```

---

## 2. Integrity Verification Procedure

Prior to deployment, verify artifact integrity:
```bash
python3 -c "
import hashlib, json, os

with open('ai/models/releases/manifest.json') as f:
    manifest = json.load(f)

for name, meta in manifest['models'].items():
    path = os.path.join('ai/models/releases', meta['filename'])
    with open(path, 'rb') as f_bin:
        actual_hash = hashlib.sha256(f_bin.read()).hexdigest()
    assert actual_hash == meta['sha256'], f'Hash mismatch on {name}!'
    print(f'[OK] {name}: Verified SHA-256')
"
```

---

## 3. Pre-Release Test Verification

Before tagging a release, run the automated test suite and benchmark suite:
```bash
# 1. Run all 85 automated tests
PYTHONPATH=. pytest -v

# 2. Run hardware benchmark suite
python3 scripts/benchmark_hardware.py

# 3. Run end-to-end demo scenarios
python3 scripts/demo_scenarios.py
```

All 3 steps must succeed without errors.

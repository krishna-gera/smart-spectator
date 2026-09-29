#!/usr/bin/env bash
# Smart Spectator - Development Environment Setup Script
set -e

echo "=== Smart Spectator Development Environment Setup ==="

# Check Python
if command -v python3 >/dev/null 2>&1; then
    echo "✔ Python3 found: $(python3 --version)"
else
    echo "❌ Python3 is required but not found."
    exit 1
fi

# Check Flutter
if command -v flutter >/dev/null 2>&1; then
    echo "✔ Flutter found: $(flutter --version | head -n 1)"
else
    echo "⚠ Flutter not found in PATH. Check ~/development/flutter/bin"
fi

# Configure Android SDK if standard location exists
if [ -d "$HOME/Library/Android/sdk" ]; then
    export ANDROID_HOME="$HOME/Library/Android/sdk"
    export PATH="$PATH:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin"
    echo "✔ Configured ANDROID_HOME=$ANDROID_HOME"
fi

# Install Python requirements
echo "Installing backend Python dependencies..."
python3 -m pip install -q fastapi uvicorn pydantic zeroconf websockets pytest opencv-python av || true

echo "=== Setup complete ==="

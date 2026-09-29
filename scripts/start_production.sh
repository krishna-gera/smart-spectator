#!/usr/bin/env bash
# Smart Spectator - Production Launch & Supervision Script
# Conforms to Section 28 of Phase 6 Master Specification.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

export SMART_SPECTATOR_ENV="production"
export DEV_MODE="false"
export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH}"

echo "======================================================================"
echo "      SMART SPECTATOR PRODUCTION HUB — SNAPDRAGON & LOCAL EDGE"
echo "======================================================================"
echo " Mode:         PRODUCTION"
echo " Version:      1.0.0"
echo " Client:       http://0.0.0.0:8000/client"
echo " Health:       http://0.0.0.0:8000/api/v1/health/detailed"
echo " Hardware:     http://0.0.0.0:8000/api/v1/system/hardware"
echo " Logging:      Rotating logs enabled in logs/hub.log"
echo "======================================================================"

python3 -m uvicorn services.hub_backend.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1 \
  --log-level warning \
  --no-access-log

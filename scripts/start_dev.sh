#!/usr/bin/env bash
# Smart Spectator - Single-Command Development Launch Script
# Conforms to Section 27 of Phase 6 Master Specification.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

export SMART_SPECTATOR_ENV="development"
export DEV_MODE="true"
export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH}"

echo "======================================================================"
echo "          SMART SPECTATOR — LOCAL VISUAL INTELLIGENCE HUB"
echo "======================================================================"
echo " Environment:  ${SMART_SPECTATOR_ENV}"
echo " Root Dir:     ${ROOT_DIR}"
echo " Client UI:    http://localhost:8000/client"
echo " Dev Console:  http://localhost:8000/"
echo " REST Docs:    http://localhost:8000/docs"
echo " Stream Port:  8554 (TCP Media Ingestion)"
echo "======================================================================"

python3 -m uvicorn services.hub_backend.main:app --host 0.0.0.0 --port 8000 --log-level info

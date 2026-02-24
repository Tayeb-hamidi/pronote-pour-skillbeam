#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Lite profile: start only the services required for the wizard flow.
docker compose up -d --build \
  traefik postgres redis minio minio-init migrate \
  api-gateway ingest generate export worker web

echo "SkillBeam Lite started on http://localhost:3784"

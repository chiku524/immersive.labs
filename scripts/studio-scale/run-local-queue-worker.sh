#!/usr/bin/env bash
# Run a queue worker on THIS machine (local CPU/GPU + Ollama/Comfy/Blender).
# Uses the same DATABASE_URL and R2 env as the remote API (Neon + Cloudflare R2).
#
# Setup:
#   cp apps/studio-worker/.env.scale.example apps/studio-worker/.env.scale
#   # Set DATABASE_URL (Neon), R2 keys, STUDIO_COMFY_URL, STUDIO_OLLAMA_URL
#   bash scripts/studio-scale/run-local-queue-worker.sh
#
# Optional: STUDIO_SCALE_ENV=/path/to/.env.scale

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${STUDIO_SCALE_ENV:-$ROOT/apps/studio-worker/.env.scale}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE — copy apps/studio-worker/.env.scale.example" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

export STUDIO_EMBEDDED_QUEUE_WORKER=0
export STUDIO_QUEUE_BACKEND="${STUDIO_QUEUE_BACKEND:-postgres}"
export STUDIO_TENANTS_BACKEND="${STUDIO_TENANTS_BACKEND:-postgres}"

cd "$ROOT/apps/studio-worker"
python -m pip install -e ".[scale]" -q
immersive-studio init-db
immersive-studio doctor --api-only
if ! immersive-studio doctor "$@"; then
  echo "WARNING: Comfy/Blender not fully ready — mock jobs may still work." >&2
fi

echo ""
echo "Starting queue worker ${STUDIO_QUEUE_WORKER_ID:-local-gpu-1} (Ctrl+C to stop)…"
exec immersive-studio queue-worker \
  --worker-id "${STUDIO_QUEUE_WORKER_ID:-local-gpu-1}" \
  --poll-interval "${STUDIO_QUEUE_POLL_INTERVAL:-1}"

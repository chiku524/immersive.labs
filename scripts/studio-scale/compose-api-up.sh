#!/usr/bin/env bash
# Build and run scale API only (Postgres via Neon URL in .env.scale; no embedded queue consumer).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${STUDIO_SCALE_ENV:-$ROOT/apps/studio-worker/.env.scale}"
exec docker compose -f "$ROOT/apps/studio-worker/docker-compose.scale.yml" \
  --env-file "$ENV_FILE" \
  up --build studio-api "$@"

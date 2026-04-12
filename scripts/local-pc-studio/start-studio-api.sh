#!/usr/bin/env bash
# Start immersive-studio serve on this PC. Run from repo root:
#   bash scripts/local-pc-studio/start-studio-api.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export STUDIO_REPO_ROOT="$ROOT"
ENV_FILE="$ROOT/apps/studio-worker/.env.local"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  echo "Loaded $ENV_FILE"
else
  echo "No $ENV_FILE — create from scripts/local-pc-studio/env.studio-worker.local.template"
fi
cd "$ROOT"
exec python -m studio_worker.cli serve --host 127.0.0.1 --port 8787

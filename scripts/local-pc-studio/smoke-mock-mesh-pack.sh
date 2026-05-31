#!/usr/bin/env bash
# Generate a mock spec + placeholder GLB pack locally (no Ollama, no ComfyUI).
# Proves the Studio → Unity import path before cloud infra or paid mesh APIs.
#
# From monorepo root:
#   bash scripts/local-pc-studio/smoke-mock-mesh-pack.sh
#
# Requires: pip install -e apps/studio-worker[dev], Blender on PATH or STUDIO_BLENDER_BIN.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export STUDIO_REPO_ROOT="$ROOT"
export STUDIO_OLLAMA_DISABLED=1

ENV_FILE="$ROOT/apps/studio-worker/.env.local"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [[ -x "$ROOT/apps/studio-worker/.venv/bin/python" ]]; then
  PY="$ROOT/apps/studio-worker/.venv/bin/python"
elif [[ -x "$ROOT/apps/studio-worker/.venv/Scripts/python.exe" ]]; then
  PY="$ROOT/apps/studio-worker/.venv/Scripts/python.exe"
else
  PY="python"
fi

PROMPT="${SMOKE_PROMPT:-wooden barrel prop for a fantasy tavern game}"
echo "=== smoke-mock-mesh-pack ==="
echo "STUDIO_REPO_ROOT=$STUDIO_REPO_ROOT"
echo "STUDIO_MESH_PROVIDER=${STUDIO_MESH_PROVIDER:-blender_placeholder}"
echo "Prompt: $PROMPT"
echo ""

"$PY" -m studio_worker.cli run-job \
  --prompt "$PROMPT" \
  --category prop \
  --style-preset toon_bold \
  --mock \
  --export-mesh

echo ""
echo "=== Next: Unity import ==="
echo "1. Find the newest folder under apps/studio-worker/output/jobs/"
echo "2. Unzip pack.zip or use the job folder directly (must contain manifest.json)."
echo "3. Unity: Immersive Labs → Import Studio Pack…"
echo "See packages/studio-unity/README.md"

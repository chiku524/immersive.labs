#!/usr/bin/env bash
# One-time bootstrap for local-first Studio (no GCE VM).
# From repo root:  bash scripts/local-pc-studio/setup-local-studio.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
USE_DOCKER=0
SKIP_NPM=0
for arg in "$@"; do
  case "$arg" in
    --docker) USE_DOCKER=1 ;;
    --skip-npm) SKIP_NPM=1 ;;
  esac
done

echo "=== Immersive Studio — local-first setup ==="
echo "Repo: $ROOT"

ENV_LOCAL="$ROOT/apps/studio-worker/.env.local"
if [[ ! -f "$ENV_LOCAL" ]]; then
  {
    echo "STUDIO_REPO_ROOT=$ROOT"
    grep -v -E '^\s*#?\s*STUDIO_REPO_ROOT=' "$ROOT/scripts/local-pc-studio/env.studio-worker.local.template" || true
  } >"$ENV_LOCAL"
  echo "Created $ENV_LOCAL"
else
  echo "Keeping existing $ENV_LOCAL"
fi

WEB_DEV="$ROOT/apps/web/.env.development.local"
if [[ ! -f "$WEB_DEV" ]]; then
  cp "$ROOT/apps/web/.env.development.local.example" "$WEB_DEV"
  echo "Created $WEB_DEV"
else
  echo "Keeping existing $WEB_DEV"
fi

if [[ "$USE_DOCKER" -eq 0 ]]; then
  VENV="$ROOT/apps/studio-worker/.venv"
  if [[ ! -x "$VENV/bin/python" && ! -x "$VENV/Scripts/python.exe" ]]; then
    python3 -m venv "$VENV" || python -m venv "$VENV"
  fi
  if [[ -x "$VENV/bin/python" ]]; then
    PY="$VENV/bin/python"
  else
    PY="$VENV/Scripts/python.exe"
  fi
  "$PY" -m pip install -q -U pip
  "$PY" -m pip install -q -e "$ROOT/apps/studio-worker[dev]"
  echo "Python worker ready: $PY"
else
  echo "Skipping venv (--docker)."
fi

if [[ "$SKIP_NPM" -eq 0 && -f "$ROOT/package.json" ]]; then
  npm install --no-audit --no-fund
fi

echo ""
echo "Next: start-comfyui → start-studio-api (or docker compose) → npm run dev"

#!/usr/bin/env bash
# Start ComfyUI for local Studio (listens on 127.0.0.1:8188).
# Usage (from monorepo root):  bash scripts/local-pc-studio/start-comfyui.sh
#
# COMFYUI_ROOT     — folder that contains main.py (default: sibling ComfyUI next to this repo).
# COMFYUI_USE_GPU  — set to 1 if you installed CUDA PyTorch; omits --cpu (required for CPU-only torch).
# On Windows, tqdm + stderr can raise [Errno 22] during sampling in some shells — disable tqdm unless TQDM_DISABLE=0.

set -euo pipefail
if [[ "${TQDM_DISABLE:-}" != "0" ]]; then
  export TQDM_DISABLE=1
fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
if [[ -n "${COMFYUI_ROOT:-}" ]]; then
  COMFY_ROOT="${COMFYUI_ROOT%/}"
else
  COMFY_ROOT="$(cd "$REPO_ROOT/.." && pwd)/ComfyUI"
fi
if [[ ! -f "$COMFY_ROOT/main.py" ]]; then
  echo "ComfyUI not found at '$COMFY_ROOT'. Clone ComfyUI there or set COMFYUI_ROOT." >&2
  exit 1
fi
VENV_PY="$COMFY_ROOT/.venv/bin/python"
if [[ ! -f "$VENV_PY" ]]; then
  VENV_PY="$COMFY_ROOT/.venv/Scripts/python.exe"
fi
if [[ ! -f "$VENV_PY" ]]; then
  echo "Missing venv python under $COMFY_ROOT/.venv — create venv and pip install -r requirements.txt" >&2
  exit 1
fi
EXTRA=(--cpu)
if [[ "${COMFYUI_USE_GPU:-}" == "1" ]]; then
  EXTRA=()
fi
LISTEN_HOST="127.0.0.1"
if [[ "${COMFYUI_DOCKER_WORKER:-}" == "1" ]]; then
  LISTEN_HOST="0.0.0.0"
  echo "COMFYUI_DOCKER_WORKER=1 — listening on 0.0.0.0:8188 (reachable from Docker studio-worker)"
fi
cd "$COMFY_ROOT"
echo "Starting ComfyUI from $COMFY_ROOT (GPU mode: ${COMFYUI_USE_GPU:-0}, listen: $LISTEN_HOST)"
exec "$VENV_PY" main.py --listen "$LISTEN_HOST" --port 8188 "${EXTRA[@]}" "$@"

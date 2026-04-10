#!/usr/bin/env bash
# Start ComfyUI for local studio texture jobs (listens on 127.0.0.1:8188).
# Prereq: clone https://github.com/comfyanonymous/ComfyUI and install its Python deps.
#
# Usage:
#   export COMFYUI_ROOT=/path/to/ComfyUI
#   ./scripts/start-comfyui-dev.sh
#
# Then in another terminal: immersive-studio doctor

set -euo pipefail
if [[ -z "${COMFYUI_ROOT:-}" ]]; then
  echo 'Set COMFYUI_ROOT to your ComfyUI repository path, e.g.: export COMFYUI_ROOT=~/src/ComfyUI'
  exit 1
fi
if [[ ! -f "${COMFYUI_ROOT}/main.py" ]]; then
  echo "COMFYUI_ROOT does not look like ComfyUI (missing main.py): ${COMFYUI_ROOT}"
  exit 1
fi
cd "${COMFYUI_ROOT}"
exec python main.py --listen 127.0.0.1 --port 8188

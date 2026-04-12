#!/bin/bash
# Run ON the GCE VM (or via: gcloud compute scp ... && gcloud compute ssh ... -- sudo bash /tmp/vm-rebuild-studio-worker.sh)
set -euo pipefail
read_metadata_attr() {
  curl -fsSL -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/attributes/${1}" 2>/dev/null || true
}
CORS="$(read_metadata_attr STUDIO_CORS_ORIGINS | tr -d '\r\n')"
COMFY_META="$(read_metadata_attr STUDIO_COMFY_URL)"
COMFY_URL="${COMFY_META:-https://comfy.immersivelabs.space}"
# Ollama on the VM host (not inside the worker container). Requires Ollama on host + OLLAMA_HOST=0.0.0.0 — see install-ollama-debian-vm.sh
OLLAMA_META="$(read_metadata_attr STUDIO_OLLAMA_URL)"
# Default: Docker bridge gateway on Linux (reliable on GCE). Override with metadata if needed
# (e.g. http://host.docker.internal:11434 when --add-host=host.docker.internal:host-gateway is used).
OLLAMA_URL="${OLLAMA_META:-http://172.17.0.1:11434}"
OLLAMA_MODEL_META="$(read_metadata_attr STUDIO_OLLAMA_MODEL)"
# tinyllama fits e2-micro disks; set metadata STUDIO_OLLAMA_MODEL=llama3.2 when you have space.
OLLAMA_MODEL="${OLLAMA_MODEL_META:-tinyllama}"
cd /opt/immersive.labs
sudo git fetch origin
sudo git reset --hard origin/main
sudo DOCKER_BUILDKIT=0 docker build -f apps/studio-worker/Dockerfile -t immersive-studio-worker:local .
sudo docker stop studio-worker 2>/dev/null || true
sudo docker rm studio-worker 2>/dev/null || true
sudo docker run -d --name studio-worker --restart unless-stopped \
  --add-host=host.docker.internal:host-gateway \
  -p 127.0.0.1:8787:8787 \
  -e STUDIO_CORS_ORIGINS="${CORS}" \
  -e STUDIO_COMFY_URL="${COMFY_URL}" \
  -e STUDIO_OLLAMA_URL="${OLLAMA_URL}" \
  -e STUDIO_OLLAMA_MODEL="${OLLAMA_MODEL}" \
  -v studio-output:/repo/apps/studio-worker/output \
  immersive-studio-worker:local
# Uvicorn may not accept connections for a second or two right after start.
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS http://127.0.0.1:8787/api/studio/health; then
    echo "OK: studio-worker rebuilt and health check passed."
    exit 0
  fi
  sleep 2
done
echo "ERROR: health check failed after container start" >&2
exit 1

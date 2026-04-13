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
# Ollama on the VM host. Default Docker mode is --network host so STUDIO_OLLAMA_URL=http://127.0.0.1:11434
# (bridge + 172.17.0.1 often hits UFW / wrong gateway / hairpin timeouts). Metadata STUDIO_DOCKER_NETWORK=bridge
# restores -p 127.0.0.1:8787:8787 + bridge gateway for Ollama.
OLLAMA_META="$(read_metadata_attr STUDIO_OLLAMA_URL)"
NET_MODE="$(read_metadata_attr STUDIO_DOCKER_NETWORK | tr '[:upper:]' '[:lower:]' | tr -d '\r\n')"
OLLAMA_MODEL_META="$(read_metadata_attr STUDIO_OLLAMA_MODEL)"
# tinyllama fits e2-micro disks; set metadata STUDIO_OLLAMA_MODEL=llama3.2 when you have space.
OLLAMA_MODEL="${OLLAMA_MODEL_META:-tinyllama}"
READ_META="$(read_metadata_attr STUDIO_OLLAMA_READ_TIMEOUT_S | tr -d '\r\n')"
READ_ENV=()
[[ -n "$READ_META" ]] && READ_ENV=(-e "STUDIO_OLLAMA_READ_TIMEOUT_S=${READ_META}")
cd /opt/immersive.labs
sudo git fetch origin
sudo git reset --hard origin/main
sudo DOCKER_BUILDKIT=0 docker build -f apps/studio-worker/Dockerfile -t immersive-studio-worker:local .
sudo docker stop studio-worker 2>/dev/null || true
sudo docker rm studio-worker 2>/dev/null || true
if [[ "$NET_MODE" == "bridge" ]]; then
  BRIDGE_GW="$(sudo docker network inspect bridge -f '{{(index .IPAM.Config 0).Gateway}}' 2>/dev/null | tr -d '\r\n')"
  [[ -z "$BRIDGE_GW" ]] && BRIDGE_GW="172.17.0.1"
  OLLAMA_URL="${OLLAMA_META:-http://${BRIDGE_GW}:11434}"
  sudo docker run -d --name studio-worker --restart unless-stopped \
    --add-host=host.docker.internal:host-gateway \
    -p 127.0.0.1:8787:8787 \
    -e STUDIO_CORS_ORIGINS="${CORS}" \
    -e STUDIO_COMFY_URL="${COMFY_URL}" \
    -e STUDIO_OLLAMA_URL="${OLLAMA_URL}" \
    -e STUDIO_OLLAMA_MODEL="${OLLAMA_MODEL}" \
    "${READ_ENV[@]}" \
    -v studio-output:/repo/apps/studio-worker/output \
    immersive-studio-worker:local
else
  OLLAMA_URL="${OLLAMA_META:-http://127.0.0.1:11434}"
  sudo docker run -d --name studio-worker --restart unless-stopped \
    --network host \
    -e STUDIO_CORS_ORIGINS="${CORS}" \
    -e STUDIO_COMFY_URL="${COMFY_URL}" \
    -e STUDIO_OLLAMA_URL="${OLLAMA_URL}" \
    -e STUDIO_OLLAMA_MODEL="${OLLAMA_MODEL}" \
    "${READ_ENV[@]}" \
    -v studio-output:/repo/apps/studio-worker/output \
    immersive-studio-worker:local \
    immersive-studio serve --host 127.0.0.1 --port 8787
fi
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

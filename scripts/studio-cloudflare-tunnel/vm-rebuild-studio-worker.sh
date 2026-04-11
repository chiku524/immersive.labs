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
cd /opt/immersive.labs
sudo git fetch origin
sudo git reset --hard origin/main
sudo DOCKER_BUILDKIT=0 docker build -f apps/studio-worker/Dockerfile -t immersive-studio-worker:local .
sudo docker stop studio-worker 2>/dev/null || true
sudo docker rm studio-worker 2>/dev/null || true
sudo docker run -d --name studio-worker --restart unless-stopped \
  -p 127.0.0.1:8787:8787 \
  -e STUDIO_CORS_ORIGINS="${CORS}" \
  -e STUDIO_COMFY_URL="${COMFY_URL}" \
  -v studio-output:/repo/apps/studio-worker/output \
  immersive-studio-worker:local
curl -fsS http://127.0.0.1:8787/api/studio/health
echo "OK: studio-worker rebuilt and health check passed."

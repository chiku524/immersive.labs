#!/bin/bash
# Intended as a GCE instance startup script (runs as root on boot).
# Idempotent: first boot installs swap, Docker, clones repo, builds image.
# If instance metadata STUDIO_CORS_ORIGINS is set, starts the studio-worker container.
# If not set after build, logs instructions; set metadata and reboot to finish.

set -euo pipefail

LOG=/var/log/immersive-studio-bootstrap.log
echo "=== immersive-studio bootstrap $(date -uIs) ===" | tee -a "$LOG"
if [[ -e /dev/ttyS0 ]]; then
  exec > >(tee -a "$LOG" /dev/ttyS0) 2>&1
else
  exec >>"$LOG" 2>&1
fi

read_metadata_attr() {
  local key="$1"
  curl -fsSL -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/attributes/${key}" 2>/dev/null || true
}

# Fully configured: just ensure Docker + container are up
if [[ -f /var/lib/immersive-studio-bootstrapped ]]; then
  systemctl start docker 2>/dev/null || true
  docker start studio-worker 2>/dev/null || true
  echo "Fast path: studio-worker start attempted."
  exit 0
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y git ca-certificates curl

# Swap (once)
if [[ ! -f /swapfile ]]; then
  fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >>/etc/fstab
  echo "Swap enabled."
fi

# Docker (once)
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sh /tmp/get-docker.sh
fi
systemctl enable docker
systemctl start docker

# Clone + build (once)
REPO_META="$(read_metadata_attr IMMERSIVE_REPO_URL)"
REPO_URL="${REPO_META:-https://github.com/chiku524/immersive.labs.git}"
if [[ ! -d /opt/immersive.labs/.git ]]; then
  mkdir -p /opt
  git clone "$REPO_URL" /opt/immersive.labs
fi
cd /opt/immersive.labs
git pull --ff-only || true

if [[ ! -f /var/lib/immersive-studio-built ]]; then
  ROOT=/opt/immersive.labs
  DF="${ROOT}/apps/studio-worker/Dockerfile"
  if [[ ! -f "${DF}" ]]; then
    echo "Missing ${DF}; clone may have failed. Listing ${ROOT}:"
    ls -la "${ROOT}" || true
    exit 1
  fi
  # BuildKit on some GCE images mishandles -f relative paths; use absolute paths + classic builder.
  DOCKER_BUILDKIT=0 docker build -f "${DF}" -t immersive-studio-worker:local "${ROOT}"
  touch /var/lib/immersive-studio-built
  echo "Docker image built."
fi

CORS="$(read_metadata_attr STUDIO_CORS_ORIGINS)"
if [[ -z "${CORS}" ]]; then
  echo "STUDIO_CORS_ORIGINS is not set in instance metadata."
  echo "Run on your laptop:"
  echo "  gcloud compute instances add-metadata immersive-studio-worker --zone=ZONE --project=PROJECT \\"
  echo "    --metadata=STUDIO_CORS_ORIGINS='https://YOUR-APP.vercel.app,https://www.example.com'"
  echo "Then reboot the VM (Console or: gcloud compute instances reset ...)."
  exit 0
fi

# ComfyUI HTTP API (textures). The worker runs INSIDE Docker: http://127.0.0.1:8188 is the *container*
# loopback, NOT the VM host — use the public URL (tunnel → host:8188) unless ComfyUI is in the same
# container network. Default matches studio_worker (https://comfy.immersivelabs.space). Override via
# instance metadata STUDIO_COMFY_URL (e.g. http://host.docker.internal:8188 if you add --add-host).
COMFY_META="$(read_metadata_attr STUDIO_COMFY_URL)"
COMFY_URL="${COMFY_META:-https://comfy.immersivelabs.space}"
OLLAMA_META="$(read_metadata_attr STUDIO_OLLAMA_URL)"
OLLAMA_URL="${OLLAMA_META:-http://host.docker.internal:11434}"
OLLAMA_MODEL_META="$(read_metadata_attr STUDIO_OLLAMA_MODEL)"
OLLAMA_MODEL="${OLLAMA_MODEL_META:-tinyllama}"

docker stop studio-worker 2>/dev/null || true
docker rm studio-worker 2>/dev/null || true
docker run -d --name studio-worker --restart unless-stopped \
  --add-host=host.docker.internal:host-gateway \
  -p 127.0.0.1:8787:8787 \
  -e STUDIO_CORS_ORIGINS="${CORS}" \
  -e STUDIO_COMFY_URL="${COMFY_URL}" \
  -e STUDIO_OLLAMA_URL="${OLLAMA_URL}" \
  -e STUDIO_OLLAMA_MODEL="${OLLAMA_MODEL}" \
  -v studio-output:/repo/apps/studio-worker/output \
  immersive-studio-worker:local

touch /var/lib/immersive-studio-bootstrapped
echo "Bootstrap complete; studio-worker running. $(date -uIs)"

#!/usr/bin/env bash
# Point the GCE studio-worker at ComfyUI on the VM host (not via Cloudflare tunnel hairpin).
#
# From your laptop (gcloud auth + SSH to immersive-studio-worker):
#   bash scripts/studio-cloudflare-tunnel/apply-gce-comfy-local-url.sh
#
# Optional:
#   CLEAR_METADATA=1  — remove STUDIO_COMFY_URL metadata so vm-rebuild uses script default
#   SKIP_REBUILD=1    — only update metadata (no git pull / docker rebuild)
#   IAP=1             — SSH via IAP when port 22 is closed publicly
#
set -euo pipefail
ZONE="${ZONE:-us-central1-a}"
VM="${VM:-immersive-studio-worker}"
_raw="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"
PROJECT="$(printf '%s' "$_raw" | tr -d '\r\n')"

GCLOUD=(gcloud compute instances)
[[ -n "$PROJECT" ]] && GCLOUD+=(--project="$PROJECT")

NET_MODE="$(
  "${GCLOUD[@]}" describe "$VM" --zone="$ZONE" \
    --format='value(metadata.items.filter(key:STUDIO_DOCKER_NETWORK).extract(value).slice(0:1))' 2>/dev/null \
    | tr '[:upper:]' '[:lower:]' | tr -d '\r\n' || true
)"
if [[ "$NET_MODE" == "bridge" ]]; then
  LOCAL_COMFY="http://host.docker.internal:8188"
else
  # Default GCE layout: studio-worker uses --network host; ComfyUI listens on 127.0.0.1:8188.
  LOCAL_COMFY="http://127.0.0.1:8188"
fi

if [[ "${CLEAR_METADATA:-0}" == "1" ]]; then
  echo "Removing STUDIO_COMFY_URL metadata (vm-rebuild will use ${LOCAL_COMFY} default)…"
  "${GCLOUD[@]}" remove-metadata "$VM" --zone="$ZONE" --keys=STUDIO_COMFY_URL 2>/dev/null || true
else
  echo "Setting STUDIO_COMFY_URL=${LOCAL_COMFY} on ${VM} (docker network: ${NET_MODE:-host})…"
  "${GCLOUD[@]}" add-metadata "$VM" --zone="$ZONE" \
    --metadata="STUDIO_COMFY_URL=${LOCAL_COMFY}"
fi

if [[ "${SKIP_REBUILD:-0}" == "1" ]]; then
  echo "SKIP_REBUILD=1 — run vm-remote-rebuild-studio-worker.sh when ready."
  exit 0
fi

echo "Rebuilding studio-worker on the VM…"
IAP="${IAP:-0}" bash "$(dirname "$0")/vm-remote-rebuild-studio-worker.sh"

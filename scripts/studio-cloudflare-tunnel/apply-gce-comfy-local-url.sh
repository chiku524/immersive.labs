#!/usr/bin/env bash
# Point the GCE studio-worker at ComfyUI on the VM host (not via Cloudflare tunnel hairpin).
#
# From your laptop (gcloud auth + SSH to immersive-studio-worker):
#   bash scripts/studio-cloudflare-tunnel/apply-gce-comfy-local-url.sh
#
# Optional:
#   CLEAR_METADATA=1  — remove STUDIO_COMFY_URL metadata so vm-rebuild uses script default
#   IAP=1             — SSH via IAP when port 22 is closed publicly
#
set -euo pipefail
ZONE="${ZONE:-us-central1-a}"
VM="${VM:-immersive-studio-worker}"
_raw="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"
PROJECT="$(printf '%s' "$_raw" | tr -d '\r\n')"
LOCAL_COMFY="http://host.docker.internal:8188"

GCLOUD=(gcloud compute instances)
[[ -n "$PROJECT" ]] && GCLOUD+=(--project="$PROJECT")

if [[ "${CLEAR_METADATA:-0}" == "1" ]]; then
  echo "Removing STUDIO_COMFY_URL metadata (vm-rebuild will use host.docker.internal default)…"
  "${GCLOUD[@]}" remove-metadata "$VM" --zone="$ZONE" --keys=STUDIO_COMFY_URL 2>/dev/null || true
else
  echo "Setting STUDIO_COMFY_URL=${LOCAL_COMFY} on ${VM}…"
  "${GCLOUD[@]}" add-metadata "$VM" --zone="$ZONE" \
    --metadata="STUDIO_COMFY_URL=${LOCAL_COMFY}"
fi

echo "Rebuilding studio-worker on the VM…"
IAP="${IAP:-0}" bash "$(dirname "$0")/vm-remote-rebuild-studio-worker.sh"

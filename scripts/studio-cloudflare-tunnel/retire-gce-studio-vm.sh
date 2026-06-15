#!/usr/bin/env bash
# Retire the GCE studio VM (stop billing). Public api.immersivelabs.space will go offline.
#
#   bash scripts/studio-cloudflare-tunnel/retire-gce-studio-vm.sh
#
# Requires: gcloud auth, compute admin on the project.
# Set RETIRE_CONFIRM=1 to skip the interactive prompt.
#
set -euo pipefail
ZONE="${ZONE:-us-central1-a}"
VM="${VM:-immersive-studio-worker}"
_raw="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"
PROJECT="$(printf '%s' "$_raw" | tr -d '\r\n')"

GCLOUD=(gcloud compute instances)
[[ -n "$PROJECT" ]] && GCLOUD+=(--project="$PROJECT")

if ! "${GCLOUD[@]}" describe "$VM" --zone="$ZONE" >/dev/null 2>&1; then
  echo "Instance $VM not found in $ZONE — already deleted or wrong project/zone."
  exit 0
fi

echo "This will DELETE GCE instance: $VM ($ZONE, project=${PROJECT:-default})"
echo "Effects:"
echo "  - api-origin.immersivelabs.space / tunnel connector on this VM stops"
echo "  - https://api.immersivelabs.space (Worker → ORIGIN_URL) will fail until you point ORIGIN_URL elsewhere"
echo "  - https://comfy.immersivelabs.space goes offline"
echo "  - Local Studio (127.0.0.1:8787 + npm run dev) is unaffected"
echo ""
if [[ "${RETIRE_CONFIRM:-}" != "1" ]]; then
  read -r -p "Type retire to confirm: " ans
  if [[ "$ans" != "retire" ]]; then
    echo "Aborted."
    exit 1
  fi
fi

echo "Deleting $VM ..."
"${GCLOUD[@]}" delete "$VM" --zone="$ZONE" --quiet

echo ""
echo "Done. VM deleted."
echo "Local workflow: bash scripts/local-pc-studio/setup-local-studio.sh"
echo "Optional later: Cloudflare Tunnel on your PC + update Worker ORIGIN_URL for public /studio."

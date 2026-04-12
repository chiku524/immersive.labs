#!/usr/bin/env bash
# From your laptop: sync /opt/immersive.labs on the GCE VM to origin/main and run vm-rebuild-studio-worker.sh.
# Requires: gcloud auth, compute.instanceAdmin or equivalent, SSH to the VM (public 22 or IAP).
#
# Defaults match other studio GCE helpers:
#   VM=immersive-studio-worker  ZONE=us-central1-a  PROJECT from gcloud config or GOOGLE_CLOUD_PROJECT
#
# IAP-only SSH (no public 22):
#   IAP=1 bash scripts/studio-cloudflare-tunnel/vm-remote-rebuild-studio-worker.sh
#
set -euo pipefail
ZONE="${ZONE:-us-central1-a}"
VM="${VM:-immersive-studio-worker}"
PROJECT="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null | tr -d '\n' || true)}"
IAP="${IAP:-0}"
GCLOUD_SSH=(gcloud compute ssh "$VM" --zone="$ZONE")
[[ -n "$PROJECT" ]] && GCLOUD_SSH+=(--project="$PROJECT")
[[ "$IAP" == "1" ]] && GCLOUD_SSH+=(--tunnel-through-iap)

"${GCLOUD_SSH[@]}" --command="set -euo pipefail; cd /opt/immersive.labs && sudo git fetch origin && sudo git reset --hard origin/main && sudo bash scripts/studio-cloudflare-tunnel/vm-rebuild-studio-worker.sh"

#!/usr/bin/env bash
# From your laptop (gcloud auth + compute permissions): copy the repo's canonical
# cloudflared ingress to the GCE VM, validate, and restart cloudflared.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ZONE="${ZONE:-us-central1-a}"
VM="${VM:-immersive-studio-worker}"
CFG="$ROOT/scripts/studio-cloudflare-tunnel/cloudflared-config-gce-immersive-api.yml"

gcloud compute scp "$CFG" "$VM:/tmp/cloudflared-config.yml" --zone="$ZONE"
gcloud compute ssh "$VM" --zone="$ZONE" --command="
  set -e
  sudo cp /tmp/cloudflared-config.yml /etc/cloudflared/config.yml
  sudo chmod 644 /etc/cloudflared/config.yml
  sudo cloudflared tunnel --config /etc/cloudflared/config.yml ingress validate
  sudo cloudflared tunnel --config /etc/cloudflared/config.yml ingress rule https://api-origin.immersivelabs.space/api/studio/health
  sudo systemctl restart cloudflared
  sleep 2
  systemctl is-active cloudflared
"

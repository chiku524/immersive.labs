#!/usr/bin/env bash
# Laptop: refresh startup script + reset VM WITHOUT full docker rebuild (fast tunnel/network recovery).
# Use when HTTP 530 / cloudflared has no connector but you do not need git pull + image rebuild.
#
#   bash scripts/studio-cloudflare-tunnel/vm-remote-recover-tunnel-light.sh
#
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ZONE="${ZONE:-us-central1-a}"
VM="${VM:-immersive-studio-worker}"
PROJECT="$(printf '%s' "${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}" | tr -d '\r\n')"

if [[ -z "$PROJECT" ]]; then
  echo "Set GOOGLE_CLOUD_PROJECT or gcloud config project" >&2
  exit 1
fi

echo "=== vm-remote-recover-tunnel-light ==="
echo "Project: $PROJECT  VM: $VM  Zone: $ZONE"
echo "Updating startup-script metadata (includes watchdog install on fast path)..."

gcloud compute instances add-metadata "$VM" \
  --zone="$ZONE" \
  --project="$PROJECT" \
  --metadata="STUDIO_INSTALL_WATCHDOG=1" \
  --metadata-from-file="startup-script=${ROOT}/scripts/studio-cloudflare-tunnel/vm-bootstrap-gce-startup.sh"

echo "Resetting VM (fast path: docker start + cloudflared + comfy + watchdog — no full rebuild)..."
gcloud compute instances reset "$VM" --zone="$ZONE" --project="$PROJECT"

echo "Waiting for instance RUNNING..."
for _w in $(seq 1 24); do
  st="$(gcloud compute instances describe "$VM" --zone="$ZONE" --project="$PROJECT" --format='get(status)' 2>/dev/null || echo UNKNOWN)"
  echo "  VM status: $st"
  [[ "$st" == "RUNNING" ]] && break
  sleep 10
done

echo "Polling https://api-origin.immersivelabs.space/api/studio/health (up to ~8 min)..."
ok=0
for i in $(seq 1 24); do
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "https://api-origin.immersivelabs.space/api/studio/health" 2>/dev/null || echo 000)"
  echo "  [$i/24] api-origin HTTP ${code}"
  if [[ "$code" == "200" ]]; then
    ok=1
    break
  fi
  if (( i % 3 == 0 )); then
    gcloud compute instances get-serial-port-output "$VM" --zone="$ZONE" --project="$PROJECT" 2>/dev/null | tail -6 || true
  fi
  sleep 20
done

if [[ "$ok" != "1" ]]; then
  echo "WARN: api-origin still not 200 — try full recover:" >&2
  echo "  bash scripts/studio-cloudflare-tunnel/vm-remote-recover-production.sh" >&2
  exit 1
fi

code_api="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "https://api.immersivelabs.space/api/studio/health" 2>/dev/null || echo 000)"
echo "api (Worker): HTTP ${code_api}"
code_comfy="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 25 "https://comfy.immersivelabs.space/system_stats" 2>/dev/null || echo 000)"
echo "comfy: HTTP ${code_comfy} (may take minutes to warm up after reboot)"

echo "=== Light recovery complete ==="

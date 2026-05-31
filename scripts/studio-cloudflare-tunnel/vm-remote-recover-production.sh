#!/usr/bin/env bash
# Laptop: push Tripo + mesh env to GCE metadata, refresh startup script, reset VM to recover tunnel + worker.
# Does NOT commit secrets — reads STUDIO_TRIPO_API_KEY from env or apps/studio-worker/.env.local (gitignored).
#
#   bash scripts/studio-cloudflare-tunnel/vm-remote-recover-production.sh
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

if [[ -z "${STUDIO_TRIPO_API_KEY:-}" ]] && [[ -f "$ROOT/apps/studio-worker/.env.local" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ROOT/apps/studio-worker/.env.local"
  set +a
fi
if [[ -z "${STUDIO_TRIPO_API_KEY:-}" ]]; then
  echo "Missing STUDIO_TRIPO_API_KEY — export it or set apps/studio-worker/.env.local" >&2
  exit 1
fi

echo "=== vm-remote-recover-production ==="
echo "Project: $PROJECT  VM: $VM  Zone: $ZONE"
echo "Setting metadata (Tripo mesh, recover-on-boot, updated startup script)..."

gcloud compute instances add-metadata "$VM" \
  --zone="$ZONE" \
  --project="$PROJECT" \
  --metadata="STUDIO_MESH_PROVIDER=tripo,STUDIO_TRIPO_TEXTURE=0,STUDIO_TRIPO_PBR=0,STUDIO_OLLAMA_DISABLED=1,STUDIO_RECOVER_ON_BOOT=1,STUDIO_TRIPO_API_KEY=${STUDIO_TRIPO_API_KEY}" \
  --metadata-from-file="startup-script=${ROOT}/scripts/studio-cloudflare-tunnel/vm-bootstrap-gce-startup.sh"

echo "Resetting VM (runs startup: docker prune, git pull, rebuild, cloudflared restart)..."
gcloud compute instances reset "$VM" --zone="$ZONE" --project="$PROJECT"

echo "Waiting for instance RUNNING..."
gcloud compute instances wait-until-running "$VM" --zone="$ZONE" --project="$PROJECT" --timeout=300

echo "Polling https://api-origin.immersivelabs.space/api/studio/health (up to ~20 min for docker build)..."
ok=0
for i in $(seq 1 60); do
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "https://api-origin.immersivelabs.space/api/studio/health" 2>/dev/null || echo 000)"
  echo "  [$i/60] api-origin HTTP ${code}"
  if [[ "$code" == "200" ]]; then
    ok=1
    break
  fi
  if (( i % 3 == 0 )); then
    gcloud compute instances get-serial-port-output "$VM" --zone="$ZONE" --project="$PROJECT" 2>/dev/null | tail -8 || true
  fi
  sleep 20
done

if [[ "$ok" != "1" ]]; then
  echo "WARN: api-origin still not 200 — check serial log:" >&2
  echo "  gcloud compute instances get-serial-port-output $VM --zone=$ZONE --project=$PROJECT | tail -80" >&2
  exit 1
fi

echo "Clearing one-shot STUDIO_RECOVER_ON_BOOT metadata..."
gcloud compute instances remove-metadata "$VM" \
  --zone="$ZONE" \
  --project="$PROJECT" \
  --keys=STUDIO_RECOVER_ON_BOOT 2>/dev/null || true

if [[ -d "$ROOT/apps/studio-edge" ]]; then
  echo "Purging edge KV health cache..."
  (cd "$ROOT/apps/studio-edge" && npx wrangler kv key delete --remote --binding=STUDIO_KV studio:health:v1 2>/dev/null || true)
  (cd "$ROOT/apps/studio-edge" && npx wrangler kv key delete --remote --binding=STUDIO_KV studio:comfy-status:v1 2>/dev/null || true)
fi

code_api="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "https://api.immersivelabs.space/api/studio/health" 2>/dev/null || echo 000)"
echo "api (Worker): HTTP ${code_api}"
echo "=== Recovery complete ==="

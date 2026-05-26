#!/usr/bin/env bash
# Push scale env to the GCE studio-worker container (API only, no embedded queue).
# Requires: apps/studio-worker/.env.scale, gcloud SSH to immersive-studio-worker.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${STUDIO_SCALE_ENV:-$ROOT/apps/studio-worker/.env.scale}"
VM="${VM:-immersive-studio-worker}"
ZONE="${ZONE:-us-central1-a}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE — run: python scripts/studio-scale/provision-scale-env.py" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

GCLOUD_SSH=(gcloud compute ssh "$VM" --zone="$ZONE")
if [[ "${IAP:-}" == "1" ]]; then
  GCLOUD_SSH+=(--tunnel-through-iap)
fi

REMOTE_ENV="/tmp/studio-scale.env"
gcloud compute scp "$ENV_FILE" "$VM:$REMOTE_ENV" --zone="$ZONE" ${IAP:+--tunnel-through-iap}

"${GCLOUD_SSH[@]}" --command="set -eo pipefail
cd /opt/immersive.labs
sudo git fetch origin && sudo git reset --hard origin/main
sudo docker build -f apps/studio-worker/Dockerfile --build-arg INSTALL_EXTRAS=scale -t immersive-studio-worker:scale .
sudo docker stop studio-worker 2>/dev/null || true
sudo docker rm studio-worker 2>/dev/null || true
grep -v '^#' "$REMOTE_ENV" | grep -v '^[[:space:]]*$' > /tmp/studio-scale.docker.env
echo STUDIO_EMBEDDED_QUEUE_WORKER=0 >> /tmp/studio-scale.docker.env
sudo docker run -d --name studio-worker --restart unless-stopped \\
  --network host \\
  --env-file /tmp/studio-scale.docker.env \\
  -v studio-output:/repo/apps/studio-worker/output \\
  immersive-studio-worker:scale \\
  immersive-studio serve --host 127.0.0.1 --port 8787
sleep 8
curl -fsS --retry 5 --retry-delay 2 http://127.0.0.1:8787/api/studio/health
echo OK
"

#!/usr/bin/env bash
# Run from your laptop (or CI) to see why https://api…/studio might fail.
# Does not change infrastructure — read-only DNS + HTTP checks.
#
#   bash scripts/studio-cloudflare-tunnel/verify-studio-public-health.sh
#   ORIGIN_HOST=api-origin.example.com WORKER_HOST=api.example.com bash ...

set -u
ORIGIN_HOST="${ORIGIN_HOST:-api-origin.immersivelabs.space}"
WORKER_HOST="${WORKER_HOST:-api.immersivelabs.space}"

resolve() {
  local h="$1"
  if command -v getent >/dev/null 2>&1; then
    getent hosts "$h" || true
  fi
  if command -v nslookup >/dev/null 2>&1; then
    nslookup "$h" 2>/dev/null | tail -n +1 | head -12 || true
  fi
}

probe() {
  local url="$1"
  local label="$2"
  echo ""
  echo "== ${label} =="
  echo "GET ${url}"
  set +e
  code=$(curl -sS -o /tmp/studio-health-body.txt -w "%{http_code}" --max-time 25 "$url" 2>/dev/null)
  curl_rc=$?
  set -e
  if [[ -z "${code}" ]]; then
    code="000"
  fi
  echo "HTTP ${code} (curl exit ${curl_rc})"
  head -c 400 /tmp/studio-health-body.txt 2>/dev/null || true
  echo ""
}

echo "=== Studio public stack check ==="
echo "Origin (tunnel → Python, should match Worker ORIGIN_URL): ${ORIGIN_HOST}"
echo "Worker (browser VITE_STUDIO_API_URL):              ${WORKER_HOST}"
echo ""
echo "== DNS: ${ORIGIN_HOST} =="
resolve "$ORIGIN_HOST"
echo ""
echo "== DNS: ${WORKER_HOST} =="
resolve "$WORKER_HOST"

probe "https://${ORIGIN_HOST}/api/studio/health" "Direct origin (must be 200 + JSON for Worker to work)"
probe "https://${WORKER_HOST}/api/studio/health" "Through Cloudflare Worker"

echo "=== If origin is not 200 ==="
echo "1. SSH to the VM that runs Docker + cloudflared."
echo "2. Run: bash scripts/studio-cloudflare-tunnel/vm-check-studio-stack.sh"
echo "3. Ensure Zero Trust public hostname ${ORIGIN_HOST} → http://127.0.0.1:8787"
echo "4. DNS: grey-cloud CNAME ${ORIGIN_HOST} → <tunnel-id>.cfargotunnel.com (see apps/studio-edge/README.md)"
echo "5. If DNS does not resolve for ${ORIGIN_HOST}, create that CNAME in Cloudflare DNS."

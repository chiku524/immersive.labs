#!/usr/bin/env bash
# Preflight before studio UI / API testing: purge edge health KV cache, sample public
# health for consistent worker_version, optionally list tunnel connectors (needs token).
#
# Usage (from repo root, Git Bash / Linux / macOS):
#   bash scripts/studio-cloudflare-tunnel/preflight-studio-public-api.sh
#
# Optional — list Cloudflare Tunnel active connections (same account as Workers):
#   export CLOUDFLARE_API_TOKEN='...'   # Account → Cloudflare Tunnel → Read
#   export CF_ACCOUNT_ID='10374f367672f4d19db430601db0926b'   # default: Workers account in wrangler.toml
#   export CF_TUNNEL_ID='52513248-a776-4f3d-b6fb-7e17c3858b2b' # immersive-labs-studio-api
#   bash scripts/studio-cloudflare-tunnel/preflight-studio-public-api.sh
#
# If repo-root `.env` exists (gitignored), it is sourced automatically for the above.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$REPO_ROOT/.env"
  set +a
fi

# shellcheck source=/dev/null
source "$SCRIPT_DIR/_cf_api_auth.sh"

STUDIO_EDGE="$REPO_ROOT/apps/studio-edge"
# STUDIO_KV id from apps/studio-edge/wrangler.toml
KV_NAMESPACE_ID="${STUDIO_KV_NAMESPACE_ID:-155442cbef05433489d804d604f74594}"
HEALTH_KV_KEY="${STUDIO_HEALTH_KV_KEY:-studio:health:v1}"
API_BASE="${STUDIO_PUBLIC_API:-https://api.immersivelabs.space}"
ACCOUNT_ID="${CF_ACCOUNT_ID:-10374f367672f4d19db430601db0926b}"
TUNNEL_ID="${CF_TUNNEL_ID:-52513248-a776-4f3d-b6fb-7e17c3858b2b}"

_py_ver() {
  python -c "import json,sys; print(json.load(sys.stdin)[\"worker_version\"])" 2>/dev/null \
    || python3 -c "import json,sys; print(json.load(sys.stdin)[\"worker_version\"])" 2>/dev/null
}

echo "== 1) Remote KV: delete ${HEALTH_KV_KEY} (edge health cache) =="
if [[ -d "$STUDIO_EDGE" ]]; then
  (cd "$STUDIO_EDGE" && npx wrangler kv key delete "$HEALTH_KV_KEY" --namespace-id="$KV_NAMESPACE_ID" --remote) \
    || echo "(wrangler delete failed — run from repo with wrangler logged in)"
else
  echo "Skip KV: missing $STUDIO_EDGE"
fi

echo ""
echo "== 2) Sample ${API_BASE}/api/studio/health (10x worker_version) =="
VERS_FILE="$(mktemp)"
trap 'rm -f "$VERS_FILE"' EXIT
for _i in $(seq 1 10); do
  if ! curl -fsS --max-time 20 "${API_BASE}/api/studio/health" | _py_ver >>"$VERS_FILE" 2>/dev/null; then
    echo "curl_failed"
  fi
  sleep 0.35
done
if [[ ! -s "$VERS_FILE" ]]; then
  echo "No successful responses."
else
  sort "$VERS_FILE" | uniq -c | sed 's/^/  /'
  UNIQ="$(sort -u "$VERS_FILE" | wc -l | tr -d ' ')"
  if [[ "$UNIQ" != "1" ]]; then
    echo ""
    echo "WARNING: Multiple worker_version values — likely multiple tunnel connectors or mixed origins."
    echo "  Zero Trust → Networks → Tunnels → immersive-labs-studio-api → Connectors: remove stray hosts."
  fi
fi

echo ""
echo "== 3) ${API_BASE}/ (service or detail) =="
curl -fsS --max-time 20 "${API_BASE}/" | python -c "import json,sys; d=json.load(sys.stdin); print(d.get('service', d.get('detail', str(d)[:120])))" 2>/dev/null \
  || curl -fsS --max-time 20 "${API_BASE}/" | head -c 200
echo ""

if [[ -n "${CLOUDFLARE_API_TOKEN:-}" || ( -n "${CF_GLOBAL_API_KEY:-}" && -n "${CF_AUTH_EMAIL:-}" ) ]]; then
  echo ""
  echo "== 4) Cloudflare tunnel (GET …/cfd_tunnel/{id} includes connections[]) =="
  URL="https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/cfd_tunnel/${TUNNEL_ID}"
  if ! _cf_api_curl "$URL" | python -m json.tool 2>/dev/null; then
    echo "(tunnel GET failed — add Tunnel Read on your API token, or set CF_AUTH_EMAIL+CF_GLOBAL_API_KEY in .env)"
    echo "    See: bash scripts/studio-cloudflare-tunnel/cf-bootstrap-user-token.sh"
  fi
else
  echo ""
  echo "== 4) Skipped: set CLOUDFLARE_API_TOKEN or CF_GLOBAL_API_KEY+CF_AUTH_EMAIL in .env =="
fi

echo ""
echo "Done."

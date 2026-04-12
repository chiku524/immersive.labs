#!/usr/bin/env bash
# Manage Cloudflare named tunnel **connectors** via API (no Zero Trust dashboard).
# Loads repo-root `.env` (gitignored).
#
# Auth (see `.env.example`):
#   - Preferred: CLOUDFLARE_API_TOKEN with **Account → Cloudflare Tunnel → Read** (and Edit to delete connectors).
#   - If your Account API token is too narrow (verify works but tunnel GET is 403), add **Global API Key**:
#       CF_AUTH_EMAIL + CF_GLOBAL_API_KEY
#     or run cf-bootstrap-user-token.sh once to mint a scoped **User** token.
#
# Usage (repo root):
#   bash scripts/studio-cloudflare-tunnel/cf-tunnel-admin.sh verify
#   bash scripts/studio-cloudflare-tunnel/cf-tunnel-admin.sh tunnel-get
#   bash scripts/studio-cloudflare-tunnel/cf-tunnel-admin.sh connector-cleanup <client_id>
#       (runs local `cloudflared tunnel cleanup`; needs `cloudflared login` cert.pem on this host)
#   bash scripts/studio-cloudflare-tunnel/cf-tunnel-admin.sh connection-delete <uuid>   # often 404; prefer connector-cleanup
#   bash scripts/studio-cloudflare-tunnel/cf-tunnel-admin.sh tunnel-wrangler-info
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

ACCOUNT_ID="${CF_ACCOUNT_ID:?Set CF_ACCOUNT_ID in repo .env}"
TUNNEL_ID="${CF_TUNNEL_ID:?Set CF_TUNNEL_ID in repo .env}"
BASE="https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}"

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" && (-z "${CF_GLOBAL_API_KEY:-}" || -z "${CF_AUTH_EMAIL:-}") ]]; then
  echo "Set CLOUDFLARE_API_TOKEN and/or CF_GLOBAL_API_KEY+CF_AUTH_EMAIL in repo .env" >&2
  exit 1
fi

_verify_bearer_token() {
  if [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
    echo "(skip verify: no CLOUDFLARE_API_TOKEN; using Global API Key auth)" >&2
    return 0
  fi
  if [[ "${CLOUDFLARE_API_TOKEN}" == cfat_* ]]; then
    _cf_api_curl "${BASE}/tokens/verify" | python -m json.tool
  else
    _cf_api_curl "https://api.cloudflare.com/client/v4/user/tokens/verify" | python -m json.tool
  fi
}

help() {
  sed -n '1,22p' "$0" | tail -n +2
}

case "${1:-help}" in
  verify)
    _verify_bearer_token
    ;;
  tunnel-get | connections | list-connections)
    # Official shape: GET …/cfd_tunnel/{id} includes `connections` (see Cloudflare Tunnel create-remote-tunnel-api doc).
    _cf_api_curl "${BASE}/cfd_tunnel/${TUNNEL_ID}" | python -m json.tool
    ;;
  connector-cleanup | cleanup-connector)
    cid="${2:?usage: $0 connector-cleanup <client_id>   (from tunnel-get: connections[].client_id; same id on multiple rows)}"
    if ! command -v cloudflared >/dev/null 2>&1; then
      echo "cloudflared not found in PATH" >&2
      exit 1
    fi
    cloudflared tunnel cleanup --connector-id "$cid" "$TUNNEL_ID"
    ;;
  connection-delete | rm-connection)
    uuid="${2:?usage: $0 connection-delete <connection_uuid>}"
    echo "Trying API DELETE (may return 404 for account tokens); prefer: $0 connector-cleanup <client_id>" >&2
    _cf_api_curl -X DELETE "${BASE}/cfd_tunnel/${TUNNEL_ID}/connections/${uuid}" | python -m json.tool
    ;;
  tunnel-wrangler-info)
    (cd "$REPO_ROOT/apps/studio-edge" && npx wrangler tunnel info "$TUNNEL_ID")
    ;;
  help | -h | --help)
    help
    ;;
  *)
    echo "Unknown command: ${1:-}" >&2
    help >&2
    exit 1
    ;;
esac

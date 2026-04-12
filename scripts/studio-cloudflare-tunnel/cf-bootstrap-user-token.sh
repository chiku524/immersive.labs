#!/usr/bin/env bash
# Create a **User API Token** (cfut_…) with Cloudflare Tunnel **Read** using your
# **Global API Key** + account email — no Zero Trust dashboard required.
#
# Prereq (one-time, from any browser session where you can open Cloudflare **My Profile**):
#   Profile → API Keys → Global API Key → View (or rotate and save securely).
#
# Put in repo-root `.env` (gitignored):
#   CF_AUTH_EMAIL=you@example.com
#   CF_GLOBAL_API_KEY=...   # Global API Key (not an API token)
#   CF_ACCOUNT_ID=10374f367672f4d19db430601db0926b
#
# Then run from repo root:
#   bash scripts/studio-cloudflare-tunnel/cf-bootstrap-user-token.sh
#
# On success, prints a new **User** token value once — append to `.env` as CLOUDFLARE_API_TOKEN=...
# Permission group: Cloudflare Tunnel / Argo Tunnel **Read** (Terraform legacy id, still valid for API).
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

EMAIL="${CF_AUTH_EMAIL:?Set CF_AUTH_EMAIL in .env}"
GKEY="${CF_GLOBAL_API_KEY:?Set CF_GLOBAL_API_KEY in .env}"
ACCOUNT_ID="${CF_ACCOUNT_ID:?Set CF_ACCOUNT_ID in .env}"
# Cloudflare Tunnel Read (legacy permission name "Argo Tunnel Read" in some tooling)
PERM_TUNNEL_READ="${CF_PERM_TUNNEL_READ:-efea2ab8357b47888938f101ae5e053f}"

BODY=$(python - <<PY
import json
account_id = "${ACCOUNT_ID}"
perm = "${PERM_TUNNEL_READ}"
body = {
  "name": "immersive-studio-tunnel-read-cli",
  "policies": [
    {
      "effect": "allow",
      "resources": {f"com.cloudflare.api.account.{account_id}": "*"},
      "permission_groups": [{"id": perm}],
    }
  ],
}
print(json.dumps(body))
PY
)

RESP=$(curl -fsS --max-time 60 -X POST "https://api.cloudflare.com/client/v4/user/tokens" \
  -H "X-Auth-Email: ${EMAIL}" \
  -H "X-Auth-Key: ${GKEY}" \
  -H "Content-Type: application/json" \
  -d "$BODY")

python - <<'PY' <<<"$RESP"
import json, sys
r = json.load(sys.stdin)
if not r.get("success"):
    print("FAILED", json.dumps(r, indent=2)[:2000])
    sys.exit(1)
val = (r.get("result") or {}).get("value")
if not val:
    print("FAILED: no token value in response", json.dumps(r, indent=2)[:2000])
    sys.exit(1)
print("")
print("Add this line to your repo .env (and remove or comment CF_GLOBAL_API_KEY if you no longer want it stored):")
print("")
print(f"CLOUDFLARE_API_TOKEN={val}")
print("")
PY

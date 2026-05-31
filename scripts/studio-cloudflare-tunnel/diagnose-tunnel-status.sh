#!/usr/bin/env bash
# Laptop: report Cloudflare tunnel connector count + public HTTP probes (read-only).
# Requires repo-root .env with CF_ACCOUNT_ID, CF_TUNNEL_ID, CLOUDFLARE_API_TOKEN (or Global API Key).
#
#   bash scripts/studio-cloudflare-tunnel/diagnose-tunnel-status.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$REPO_ROOT/.env"
  set +a
fi

echo "=== Cloudflare tunnel (API) ==="
_tunnel_json="$(bash "$SCRIPT_DIR/cf-tunnel-admin.sh" tunnel-get 2>/dev/null || true)"
if [[ -n "$_tunnel_json" ]]; then
  printf '%s' "$_tunnel_json" | python - <<'PY'
import json, sys
try:
    d = json.load(sys.stdin)
except json.JSONDecodeError:
    print("(could not parse tunnel-get JSON — check .env auth)")
    raise SystemExit(0)
r = d.get("result") or {}
conns = r.get("connections") or []
print(f"  tunnel: {r.get('name')}  status={r.get('status')}  connectors={len(conns)}")
if not conns:
    print("  >>> NO CONNECTORS — cloudflared is not running on the VM (HTTP 530 on api/comfy).")
    print("  >>> Fix: GCP Console → immersive-studio-worker → SSH in browser →")
    print("      sudo bash /opt/immersive.labs/scripts/studio-cloudflare-tunnel/vm-recover-tunnel-and-docker.sh")
else:
    for c in conns[:5]:
        print(f"  - {c.get('client_id','?')} @ {c.get('origin_ip','?')} colo={c.get('colo_name','?')}")
PY
else
  echo "  (tunnel-get failed — set CF_ACCOUNT_ID, CF_TUNNEL_ID, CLOUDFLARE_API_TOKEN in repo .env)"
fi

echo ""
bash "$SCRIPT_DIR/verify-studio-public-health.sh"

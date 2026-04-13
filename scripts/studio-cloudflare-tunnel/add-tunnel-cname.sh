#!/usr/bin/env bash
# Create or replace a CNAME <subdomain>.<zone> -> <tunnel-id>.cfargotunnel.com using the Cloudflare API.
# Use this when `cloudflared tunnel route dns` attaches the name to the wrong zone (multiple accounts).
#
# Prerequisites:
#   - Zone is on the SAME Cloudflare account as the token.
#   - CLOUDFLARE_API_TOKEN with Zone > DNS > Edit for that zone.
#
# Usage:
#   export CLOUDFLARE_API_TOKEN='...'
#   bash scripts/studio-cloudflare-tunnel/add-tunnel-cname.sh api-origin 52513248-a776-4f3d-b6fb-7e17c3858b2b immersivelabs.space
#
# Or the same via env (positional args win when set):
#   SUBDOMAIN=api-origin TUNNEL_ID=52513248-... ZONE=immersivelabs.space bash scripts/.../add-tunnel-cname.sh
#
# Tunnel CNAME is often better DNS-only (grey cloud) to avoid Cloudflare HTTP 524 on slow origins:
#   CLOUDFLARE_TUNNEL_CNAME_PROXIED=false bash scripts/.../add-tunnel-cname.sh api-origin <uuid> immersivelabs.space
#
# Git Bash: if curl fails with "URL rejected: Malformed input", pull latest (MSYS2_ARG_CONV_EXCL + id trim).
#
set -euo pipefail

# Git Bash / MSYS can rewrite arguments that look like paths; curl then sees a broken URL (error 3).
export MSYS2_ARG_CONV_EXCL="*"

PY="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)"
if [[ -z "$PY" ]]; then
  echo "Need python3 or python in PATH to parse Cloudflare JSON." >&2
  exit 1
fi

SUB="${1:-${SUBDOMAIN:-}}"
TUNNEL_ID="${2:-${TUNNEL_ID:-}}"
ZONE_NAME="${3:-${ZONE:-immersivelabs.space}}"
if [[ -z "$SUB" ]]; then
  echo "Missing DNS label: pass as first arg (e.g. api-origin) or set SUBDOMAIN=api-origin" >&2
  echo "Usage: $0 <dns-label> <tunnel-uuid> [zone]" >&2
  exit 1
fi
if [[ -z "$TUNNEL_ID" ]]; then
  echo "Missing tunnel UUID: pass as second arg or set TUNNEL_ID=..." >&2
  exit 1
fi
TOKEN="${CLOUDFLARE_API_TOKEN:?set CLOUDFLARE_API_TOKEN (Zone DNS Edit)}"

BASE="https://api.cloudflare.com/client/v4"
CNAME_TARGET="${TUNNEL_ID}.cfargotunnel.com"
FQDN="${SUB}.${ZONE_NAME}"

hdr=(-H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json")

echo "Resolving zone ${ZONE_NAME}..."
zones_json="$(curl -fsS "${hdr[@]}" "${BASE}/zones?name=${ZONE_NAME}")"
zone_id="$("$PY" -c "import json,sys; d=json.load(sys.stdin); r=d.get('result')or[]; print(r[0]['id'] if r else '')" <<<"$zones_json" | tr -d '\r\n')"
if [[ -z "$zone_id" ]]; then
  echo "Zone not found: ${ZONE_NAME}" >&2
  exit 1
fi
echo "zone_id=${zone_id}"

echo "Listing existing ${FQDN}..."
list_json="$(curl -fsS "${hdr[@]}" "${BASE}/zones/${zone_id}/dns_records?name=${FQDN}")"
while IFS= read -r rid || [[ -n "${rid:-}" ]]; do
  rid="$(printf '%s' "$rid" | tr -d '\r\n')"
  [[ -z "$rid" ]] && continue
  echo "Deleting record id=${rid}"
  del_url="${BASE}/zones/${zone_id}/dns_records/${rid}"
  curl -fsS "${hdr[@]}" -X DELETE "$del_url" >/dev/null
done < <("$PY" -c "
import json,sys
d=json.load(sys.stdin)
for r in d.get('result')or[]:
    if r.get('type') in ('A','AAAA','CNAME'):
        print(r['id'])
" <<<"$list_json")

prox_note="proxied"
case "${CLOUDFLARE_TUNNEL_CNAME_PROXIED:-true}" in
  0|false|False|FALSE|no|No|NO) prox_note="DNS only (grey cloud)" ;;
esac
echo "Creating CNAME ${FQDN} -> ${CNAME_TARGET} (${prox_note})..."
body="$(
  SUB="$SUB" CNAME_TARGET="$CNAME_TARGET" TUNNEL_ID="$TUNNEL_ID" \
    CLOUDFLARE_TUNNEL_CNAME_PROXIED="${CLOUDFLARE_TUNNEL_CNAME_PROXIED:-true}" \
    "$PY" -c "
import json, os
raw = os.environ.get('CLOUDFLARE_TUNNEL_CNAME_PROXIED', 'true').lower()
proxied = raw not in ('0', 'false', 'no', 'off')
print(json.dumps({
  'type': 'CNAME',
  'name': os.environ['SUB'],
  'content': os.environ['CNAME_TARGET'],
  'ttl': 1,
  'proxied': proxied,
  'comment': 'cloudflared tunnel ' + os.environ['TUNNEL_ID'],
}))
")"
resp="$(curl -fsS "${hdr[@]}" -X POST "${BASE}/zones/${zone_id}/dns_records" -d "$body")"
"$PY" -c "
import json, sys
d = json.load(sys.stdin)
if not d.get('success'):
    sys.stderr.write(json.dumps(d.get('errors'), indent=2) + '\n')
    sys.exit(1)
r = d.get('result') or {}
print('Created CNAME', r.get('name'), '->', r.get('content'))
" <<<"$resp"
echo "Next: nslookup ${FQDN} (after propagation)"

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
#   bash scripts/studio-cloudflare-tunnel/add-tunnel-cname.sh comfy 52513248-a776-4f3d-b6fb-7e17c3858b2b immersivelabs.space
#
set -euo pipefail

PY="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)"
if [[ -z "$PY" ]]; then
  echo "Need python3 or python in PATH to parse Cloudflare JSON." >&2
  exit 1
fi

SUB="${1:?first arg: DNS label (e.g. comfy)}"
TUNNEL_ID="${2:?second arg: tunnel UUID}"
ZONE_NAME="${3:-immersivelabs.space}"
TOKEN="${CLOUDFLARE_API_TOKEN:?set CLOUDFLARE_API_TOKEN (Zone DNS Edit)}"

BASE="https://api.cloudflare.com/client/v4"
CNAME_TARGET="${TUNNEL_ID}.cfargotunnel.com"
FQDN="${SUB}.${ZONE_NAME}"

hdr=(-H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json")

echo "Resolving zone ${ZONE_NAME}..."
zones_json="$(curl -fsS "${hdr[@]}" "${BASE}/zones?name=${ZONE_NAME}")"
zone_id="$("$PY" -c "import json,sys; d=json.load(sys.stdin); r=d.get('result')or[]; print(r[0]['id'] if r else '')" <<<"$zones_json")"
if [[ -z "$zone_id" ]]; then
  echo "Zone not found: ${ZONE_NAME}" >&2
  exit 1
fi
echo "zone_id=${zone_id}"

echo "Listing existing ${FQDN}..."
list_json="$(curl -fsS "${hdr[@]}" "${BASE}/zones/${zone_id}/dns_records?name=${FQDN}")"
while read -r rid; do
  [[ -z "$rid" ]] && continue
  echo "Deleting record id=${rid}"
  curl -fsS "${hdr[@]}" -X DELETE "${BASE}/zones/${zone_id}/dns_records/${rid}" >/dev/null
done < <("$PY" -c "
import json,sys
d=json.load(sys.stdin)
for r in d.get('result')or[]:
    if r.get('type') in ('A','AAAA','CNAME'):
        print(r['id'])
" <<<"$list_json")

echo "Creating CNAME ${FQDN} -> ${CNAME_TARGET} (proxied)..."
body="$("$PY" -c "
import json
print(json.dumps({
  'type':'CNAME',
  'name':'${SUB}',
  'content':'${CNAME_TARGET}',
  'ttl': 1,
  'proxied': True,
  'comment': 'cloudflared tunnel ${TUNNEL_ID}',
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

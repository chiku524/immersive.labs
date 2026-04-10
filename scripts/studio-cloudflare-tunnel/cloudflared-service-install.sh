#!/usr/bin/env bash
# Run ON the GCP VM as root after creating a *remotely managed* tunnel in Cloudflare Zero Trust.
# Dashboard: Zero Trust → Networks → Tunnels → Create tunnel → choose Debian/VM → copy the
#   "sudo cloudflared service install …" token (long JWT).
#
# Usage:
#   sudo ./cloudflared-service-install.sh 'eyJhIjoi...'
# Or:
#   sudo CLOUDFLARE_TUNNEL_TOKEN='eyJhIjoi...' ./cloudflared-service-install.sh

set -euo pipefail

if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "Must run as root: sudo $0 '<token>'" >&2
  exit 1
fi

TOKEN=${1:-${CLOUDFLARE_TUNNEL_TOKEN:-}}
if [[ -z "${TOKEN}" ]]; then
  echo "Usage: sudo $0 '<cloudflared service install token>'" >&2
  echo "Get the token from Cloudflare Zero Trust when you create the tunnel (Debian install command)." >&2
  exit 1
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared not found. Run install-cloudflared-debian.sh first (not as root)." >&2
  exit 1
fi

cloudflared service install "${TOKEN}"
systemctl enable cloudflared 2>/dev/null || true
systemctl restart cloudflared
systemctl --no-pager status cloudflared || true
echo "Done. In Zero Trust, set Public hostname → http://127.0.0.1:8787 (studio worker must be listening)."

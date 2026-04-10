#!/usr/bin/env bash
# Run ON the GCP VM (Ubuntu/Debian). Installs cloudflared from Cloudflare's apt repo.
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  echo "Run as a normal user; the script will use sudo where needed." >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "Installing curl…" >&2
  sudo apt-get update -qq
  sudo apt-get install -y curl
fi

sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" \
  | sudo tee /etc/apt/sources.list.d/cloudflared.list >/dev/null

sudo apt-get update -qq
sudo apt-get install -y cloudflared

cloudflared --version
echo "cloudflared installed. Next: create a tunnel in Cloudflare Zero Trust and run cloudflared-service-install.sh with the token."

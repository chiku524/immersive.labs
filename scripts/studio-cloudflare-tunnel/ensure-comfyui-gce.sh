#!/bin/bash
# Idempotent: start ComfyUI systemd service, or install when STUDIO_INSTALL_COMFY=1 metadata is set.
# Run as root on the GCE VM (called from vm-bootstrap fast path / recover).
set -euo pipefail

read_metadata_attr() {
  curl -fsSL -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/attributes/${1}" 2>/dev/null || true
}

REPO="${REPO:-/opt/immersive.labs}"
INSTALL_SCRIPT="${REPO}/scripts/studio-cloudflare-tunnel/install-comfyui-gce.sh"

if systemctl list-unit-files comfyui.service >/dev/null 2>&1; then
  systemctl enable comfyui.service 2>/dev/null || true
  systemctl restart comfyui.service 2>/dev/null || systemctl start comfyui.service || true
  echo "comfyui.service restarted."
  exit 0
fi

install_flag="$(read_metadata_attr STUDIO_INSTALL_COMFY | tr -d '\r\n')"
if [[ "$install_flag" != "1" ]]; then
  echo "comfyui.service not installed; set instance metadata STUDIO_INSTALL_COMFY=1 and reboot."
  exit 0
fi

if [[ ! -f "$INSTALL_SCRIPT" ]]; then
  echo "Missing ${INSTALL_SCRIPT} — git pull /opt/immersive.labs first." >&2
  exit 1
fi

echo "STUDIO_INSTALL_COMFY=1 — running install-comfyui-gce.sh (first run may download ~4 GiB checkpoint)…"
bash "$INSTALL_SCRIPT"

#!/usr/bin/env bash
# Install periodic studio stack watchdog on GCE (systemd timer, every 5 minutes).
# Run as root on the VM, or via vm-bootstrap fast path.
set -euo pipefail

if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

ROOT="${ROOT:-/opt/immersive.labs}"
WATCHDOG_SRC="$ROOT/scripts/studio-cloudflare-tunnel/studio-stack-watchdog.sh"
if [[ ! -f "$WATCHDOG_SRC" ]]; then
  echo "Missing $WATCHDOG_SRC — clone repo to /opt/immersive.labs first" >&2
  exit 1
fi

install -m 0755 "$WATCHDOG_SRC" /usr/local/bin/studio-stack-watchdog.sh

cat >/etc/systemd/system/studio-stack-watchdog.service <<'EOF'
[Unit]
Description=Immersive Studio stack watchdog (tunnel, Docker, Comfy)
After=network-online.target docker.service cloudflared.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/studio-stack-watchdog.sh
EOF

cat >/etc/systemd/system/studio-stack-watchdog.timer <<'EOF'
[Unit]
Description=Run Immersive Studio stack watchdog every 5 minutes

[Timer]
OnBootSec=3min
OnUnitActiveSec=5min
AccuracySec=1min
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable studio-stack-watchdog.timer
systemctl start studio-stack-watchdog.timer
systemctl start studio-stack-watchdog.service || true

echo "studio-stack-watchdog timer enabled (every 5 min). Status:"
systemctl is-active studio-stack-watchdog.timer || true

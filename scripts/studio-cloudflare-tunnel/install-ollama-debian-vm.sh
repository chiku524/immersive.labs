#!/usr/bin/env bash
# Install Ollama on a Debian/Ubuntu VM host so the **Docker** studio-worker can reach it at
# http://172.17.0.1:11434 (default in vm-rebuild) or http://host.docker.internal:11434 (metadata override).
#
# Run on the GCE VM as a user with sudo:
#   curl -fsSL …/install-ollama-debian-vm.sh | bash
#   or: sudo bash scripts/studio-cloudflare-tunnel/install-ollama-debian-vm.sh
#
# Sets OLLAMA_HOST=0.0.0.0:11434 so the Docker bridge can reach the daemon (not only 127.0.0.1).
# Default model pull: llama3.2 (override with OLLAMA_FIRST_PULL=model:tag).
#
set -euo pipefail

# Default to a small model suitable for e2-micro + 30 GiB disk; use OLLAMA_FIRST_PULL=llama3.2 on larger disks.
FIRST_PULL="${OLLAMA_FIRST_PULL:-tinyllama}"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Re-run with sudo or as root." >&2
  exit 1
fi

curl -fsSL https://ollama.com/install.sh | sh

mkdir -p /etc/systemd/system/ollama.service.d
cat >/etc/systemd/system/ollama.service.d/override.conf <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF

systemctl daemon-reload
systemctl enable ollama
systemctl restart ollama

# Wait for socket
for _ in $(seq 1 30); do
  if curl -fsS --max-time 2 "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

ollama pull "$FIRST_PULL"

echo "OK: Ollama listening on 0.0.0.0:11434; pulled ${FIRST_PULL}."
echo "Recreate studio-worker with STUDIO_OLLAMA_URL=http://172.17.0.1:11434 (default in vm-rebuild) or host.docker.internal; see vm-rebuild-studio-worker.sh."
echo "If the worker still cannot reach Ollama, check host firewall (ufw): allow traffic from docker0 to port 11434."

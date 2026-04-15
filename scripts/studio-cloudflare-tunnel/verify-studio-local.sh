#!/usr/bin/env bash
# Run on the host where Ollama + studio-worker listen (VM or dev PC). No systemd required.
set +e

OLLAMA_URL="${STUDIO_OLLAMA_URL:-http://127.0.0.1:11434}"
WORKER_URL="${STUDIO_WORKER_HEALTH_URL:-http://127.0.0.1:8787}"

echo "=== Ollama ($OLLAMA_URL/api/tags) ==="
if curl -sS -m 8 "${OLLAMA_URL}/api/tags" | head -c 800; then
  echo
else
  echo "(curl failed — is Ollama running?)"
fi

echo ""
echo "=== Studio worker ($WORKER_URL/api/studio/health) ==="
if curl -sS -m 15 "${WORKER_URL}/api/studio/health"; then
  echo
else
  echo "(curl failed — is immersive-studio listening on 8787?)"
fi

echo ""
echo "=== cloudflared process (best-effort) ==="
if command -v systemctl >/dev/null 2>&1; then
  systemctl is-active cloudflared 2>/dev/null || echo "systemctl: cloudflared not active or not installed as unit"
  journalctl -u cloudflared -n 25 --no-pager 2>/dev/null || true
elif command -v sc.exe >/dev/null 2>&1; then
  sc query cloudflared 2>/dev/null || sc query Cloudflared 2>/dev/null || echo "No Windows service 'cloudflared' — run tunnel manually or install as service."
elif command -v pgrep >/dev/null 2>&1; then
  pgrep -a cloudflared 2>/dev/null || echo "No cloudflared process found (pgrep)."
else
  echo "No systemctl/sc/pgrep; check Task Manager or Docker for cloudflared."
fi

echo ""
echo "Done."

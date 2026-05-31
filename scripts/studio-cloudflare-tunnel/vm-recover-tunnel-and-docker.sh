#!/usr/bin/env bash
# Run ON the GCE studio VM via GCP Console → SSH in browser (paste entire script).
# Restores api-origin / comfy tunnels when cloudflared or Docker stopped (HTTP 530).
#
#   sudo bash vm-recover-tunnel-and-docker.sh
#
# Safe to re-run; idempotent start/restart only.

set -u

echo "=== vm-recover-tunnel-and-docker $(date -uIs) ==="

echo ""
echo "== 1/4 Docker studio-worker =="
if command -v docker >/dev/null 2>&1; then
  if docker ps -a --format '{{.Names}}' | grep -qx 'studio-worker'; then
    docker start studio-worker 2>/dev/null || true
    sleep 2
    docker ps --filter name=studio-worker --no-trunc || true
  else
    echo "No studio-worker container — run vm-rebuild-studio-worker.sh from your laptop, or see vm-bootstrap-gce-startup.sh"
  fi
else
  echo "docker not installed"
fi

echo ""
echo "== 2/4 Local API health (tunnel target :8787) =="
if curl -fsS --max-time 8 http://127.0.0.1:8787/api/studio/health >/tmp/recover-health.json; then
  echo "OK http://127.0.0.1:8787"
  head -c 200 /tmp/recover-health.json
  echo ""
else
  echo "FAIL — worker not on 8787. Check: docker logs studio-worker --tail 40"
fi

echo ""
echo "== 3/4 cloudflared (tunnel connector) =="
if systemctl list-unit-files cloudflared.service >/dev/null 2>&1; then
  systemctl restart cloudflared
  sleep 3
  systemctl is-active cloudflared || true
  systemctl --no-pager -l status cloudflared 2>/dev/null | head -20 || true
else
  echo "No cloudflared systemd unit."
  echo "Install: scripts/studio-cloudflare-tunnel/install-cloudflared-debian.sh"
  echo "Then: cloudflared-service-install.sh with your tunnel token"
fi

echo ""
echo "== 4/4 ComfyUI (:8188) =="
if systemctl list-unit-files comfyui.service >/dev/null 2>&1; then
  systemctl restart comfyui 2>/dev/null || systemctl start comfyui || true
fi
if curl -fsS --max-time 8 http://127.0.0.1:8188/system_stats >/dev/null 2>&1; then
  echo "OK ComfyUI on 127.0.0.1:8188"
else
  echo "ComfyUI not listening — set STUDIO_INSTALL_COMFY=1 metadata and reboot, or run ensure-comfyui-gce.sh"
  echo "Tunnel hostname comfy.immersivelabs.space needs ingress → http://127.0.0.1:8188 in cloudflared config."
fi

echo ""
echo "=== From your laptop (after ~30s) ==="
echo "  curl -sS -o /dev/null -w '%{http_code}\\n' https://api-origin.immersivelabs.space/api/studio/health"
echo "  curl -sS -o /dev/null -w '%{http_code}\\n' https://api.immersivelabs.space/api/studio/health"
echo ""
echo "If still 530: Zero Trust → Tunnels → Connectors — remove stale connectors; only this VM should be listed."
echo "Purge edge KV cache: cd apps/studio-edge && npx wrangler kv key delete --remote --binding=STUDIO_KV studio:health:v1"
echo "=== Done ==="

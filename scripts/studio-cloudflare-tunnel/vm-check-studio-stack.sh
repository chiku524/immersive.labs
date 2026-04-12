#!/usr/bin/env bash
# Run ON the studio GCE VM (SSH) after cloning or with repo at /opt/immersive.labs.
# Checks: cloudflared, Docker container, local health, Blender inside the image.
#
#   curl -fsSL https://raw.githubusercontent.com/.../vm-check-studio-stack.sh | sudo bash
# or copy this file to the VM and:  sudo bash vm-check-studio-stack.sh

set -u

echo "=== vm-check-studio-stack $(date -uIs) ==="

echo ""
echo "== cloudflared (tunnel must be active for api-origin HTTPS) =="
if systemctl list-unit-files cloudflared.service >/dev/null 2>&1; then
  systemctl is-active cloudflared 2>/dev/null || echo "cloudflared: not active"
  systemctl --no-pager -l status cloudflared 2>/dev/null | head -30 || true
else
  echo "No cloudflared systemd unit — install with install-cloudflared-debian.sh + cloudflared-service-install.sh"
fi

echo ""
echo "== Docker: studio-worker container =="
if command -v docker >/dev/null 2>&1; then
  docker ps -a --filter name=studio-worker --no-trunc || true
else
  echo "docker not installed"
fi

echo ""
echo "== Local Python API (what the tunnel should target) =="
if curl -fsS --max-time 5 http://127.0.0.1:8787/api/studio/health >/tmp/local-health.json 2>/dev/null; then
  echo "OK http://127.0.0.1:8787/api/studio/health"
  head -c 300 /tmp/local-health.json
  echo ""
else
  echo "FAIL — nothing on 127.0.0.1:8787. Start the worker, e.g.:"
  echo "  docker start studio-worker"
  echo "  # or first-time: see vm-bootstrap-gce-startup.sh / vm-rebuild-studio-worker.sh"
fi

echo ""
echo "== Blender inside studio-worker image (mesh export; not a daemon — must exist in PATH) =="
if docker ps --filter name=studio-worker --filter status=running --format '{{.Names}}' | grep -q .; then
  if docker exec studio-worker test -x /usr/local/bin/blender 2>/dev/null; then
    docker exec studio-worker /usr/local/bin/blender --version || true
  else
    echo "/usr/local/bin/blender missing in container — rebuild apps/studio-worker/Dockerfile"
  fi
else
  echo "studio-worker container not running — skip blender exec"
fi

echo ""
echo "=== Done ==="

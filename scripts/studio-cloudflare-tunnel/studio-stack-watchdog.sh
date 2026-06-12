#!/usr/bin/env bash
# Run on the GCE VM (root cron/systemd). Restarts stack when tunnel, Docker, or host networking fails.
# GCE VMs do not "sleep" — HTTP 530 usually means cloudflared lost its connector or the NIC hung.
set -euo pipefail

LOG_TAG="studio-watchdog"
STATE_DIR="/var/lib/immersive-studio-watchdog"
mkdir -p "$STATE_DIR"

log() {
  logger -t "$LOG_TAG" "$*"
  echo "[$(date -uIs)] $*"
}

metadata_ok() {
  curl -fsS --max-time 3 -H "Metadata-Flavor: Google" \
    "http://169.254.169.254/computeMetadata/v1/instance/id" >/dev/null 2>&1
}

internet_ok() {
  curl -fsS --max-time 5 -o /dev/null https://1.1.1.1/cdn-cgi/trace 2>/dev/null \
    || curl -fsS --max-time 5 -o /dev/null https://cloudflare.com 2>/dev/null
}

local_api_ok() {
  curl -fsS --max-time 5 "http://127.0.0.1:8787/api/studio/health" >/dev/null 2>&1
}

local_comfy_ok() {
  curl -fsS --max-time 8 "http://127.0.0.1:8188/system_stats" >/dev/null 2>&1
}

cloudflared_active() {
  systemctl is-active --quiet cloudflared 2>/dev/null
}

docker_worker_running() {
  docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'studio-worker'
}

bump_fail() {
  local key="$1"
  local f="$STATE_DIR/${key}.fail"
  local n=0
  [[ -f "$f" ]] && n="$(cat "$f" 2>/dev/null || echo 0)"
  n=$((n + 1))
  echo "$n" >"$f"
  echo "$n"
}

clear_fail() {
  rm -f "$STATE_DIR/$1.fail"
}

maybe_reboot() {
  local key="$1"
  local n
  n="$(bump_fail "$key")"
  log "FAIL count for ${key}: ${n}"
  if (( n >= 3 )); then
    log "Rebooting VM after repeated ${key} failures (network/tunnel recovery exhausted)"
    sync || true
    sleep 2
    systemctl reboot || reboot -f
  fi
}

restart_stack() {
  log "Restarting Docker, studio-worker, ComfyUI, cloudflared"
  systemctl start docker 2>/dev/null || true
  docker start studio-worker 2>/dev/null || true
  if [[ -x /opt/immersive.labs/scripts/studio-cloudflare-tunnel/ensure-comfyui-gce.sh ]]; then
    bash /opt/immersive.labs/scripts/studio-cloudflare-tunnel/ensure-comfyui-gce.sh || true
  elif systemctl list-unit-files comfyui.service >/dev/null 2>&1; then
    systemctl restart comfyui 2>/dev/null || true
  fi
  if systemctl list-unit-files cloudflared.service >/dev/null 2>&1; then
    systemctl restart cloudflared 2>/dev/null || true
  fi
}

# --- checks ---
if ! metadata_ok; then
  log "Metadata server unreachable — NIC or network stack may be hung"
  systemctl restart systemd-networkd 2>/dev/null || true
  systemctl restart google-guest-agent 2>/dev/null || true
  sleep 5
  if ! metadata_ok; then
    maybe_reboot "metadata"
    exit 1
  fi
fi
clear_fail "metadata"

if ! internet_ok; then
  log "No outbound internet — restarting networking"
  systemctl restart systemd-networkd 2>/dev/null || true
  sleep 5
  if ! internet_ok; then
    maybe_reboot "internet"
    exit 1
  fi
fi
clear_fail "internet"

systemctl start docker 2>/dev/null || true

if ! docker_worker_running; then
  log "studio-worker container not running — docker start"
  docker start studio-worker 2>/dev/null || true
  sleep 3
fi

if ! local_api_ok; then
  log "Local API health failed on :8787"
  restart_stack
  sleep 8
  if ! local_api_ok; then
    maybe_reboot "local_api"
    exit 1
  fi
fi
clear_fail "local_api"

if systemctl list-unit-files comfyui.service >/dev/null 2>&1; then
  if ! local_comfy_ok; then
    log "ComfyUI :8188 not responding — ensure/restart comfyui"
    if [[ -x /opt/immersive.labs/scripts/studio-cloudflare-tunnel/ensure-comfyui-gce.sh ]]; then
      bash /opt/immersive.labs/scripts/studio-cloudflare-tunnel/ensure-comfyui-gce.sh || true
    else
      systemctl restart comfyui 2>/dev/null || true
    fi
  fi
fi

if ! cloudflared_active; then
  log "cloudflared inactive — restart"
  systemctl restart cloudflared 2>/dev/null || true
  sleep 5
fi

if ! cloudflared_active; then
  maybe_reboot "cloudflared"
  exit 1
fi
clear_fail "cloudflared"

log "OK: metadata, internet, local API, cloudflared"
exit 0

#!/bin/bash
# Install ComfyUI on a GCE VM: /opt/ComfyUI, venv, CPU PyTorch, SD1.5 checkpoint, systemd on 127.0.0.1:8188.
# Run as root (e.g. sudo bash install-comfyui-gce.sh). Idempotent: safe to re-run.
#
# Requires: git, curl, ca-certificates (apt install -y git curl ca-certificates)
# After: systemctl enable --now comfyui
# Tunnel should map comfy.immersivelabs.space → http://127.0.0.1:8188 (see cloudflared-config-gce-immersive-api.yml).

set -euo pipefail

COMFY_ROOT="${COMFY_ROOT:-/opt/ComfyUI}"
# Match studio-worker default STUDIO_COMFY_CHECKPOINT for sd15 (safetensors).
CKPT_URL="${CKPT_URL:-https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive/resolve/main/v1-5-pruned-emaonly.safetensors}"
CKPT_NAME="${CKPT_NAME:-v1-5-pruned-emaonly.safetensors}"
COMFY_USER="${COMFY_USER:-comfy}"

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  git \
  ca-certificates \
  curl \
  python3 \
  python3-venv \
  python3-dev \
  build-essential \
  libgl1 \
  libglib2.0-0

if ! id -u "${COMFY_USER}" >/dev/null 2>&1; then
  useradd --system --shell /bin/bash --home /var/lib/comfy --create-home "${COMFY_USER}"
fi

mkdir -p "${COMFY_ROOT}"
chown "${COMFY_USER}:${COMFY_USER}" "${COMFY_ROOT}"

if [[ ! -f "${COMFY_ROOT}/main.py" ]]; then
  sudo -u "${COMFY_USER}" git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git "${COMFY_ROOT}"
else
  sudo -u "${COMFY_USER}" git -C "${COMFY_ROOT}" pull --ff-only || true
fi

VENV="${COMFY_ROOT}/venv"
if [[ ! -x "${VENV}/bin/python" ]]; then
  sudo -u "${COMFY_USER}" python3 -m venv "${VENV}"
fi

# CPU wheels (no CUDA on typical e2 instances)
sudo -u "${COMFY_USER}" "${VENV}/bin/pip" install --upgrade pip
sudo -u "${COMFY_USER}" "${VENV}/bin/pip" install torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/cpu
sudo -u "${COMFY_USER}" "${VENV}/bin/pip" install -r "${COMFY_ROOT}/requirements.txt"

CKPT_DIR="${COMFY_ROOT}/models/checkpoints"
mkdir -p "${CKPT_DIR}"
chown -R "${COMFY_USER}:${COMFY_USER}" "${COMFY_ROOT}/models"

CKPT_PATH="${CKPT_DIR}/${CKPT_NAME}"
CKPT_BYTES="$(stat -c%s "${CKPT_PATH}" 2>/dev/null || echo 0)"
# Full SD1.5 pruned ckpt is ~4 GiB; skip re-download if present.
if [[ "${CKPT_BYTES}" -lt 3000000000 ]]; then
  echo "Downloading checkpoint ${CKPT_NAME} (several GB; resumable)…"
  sudo -u "${COMFY_USER}" curl -fL --retry 10 --retry-delay 15 -C - -o "${CKPT_PATH}.part" "${CKPT_URL}"
  mv -f "${CKPT_PATH}.part" "${CKPT_PATH}"
  chown "${COMFY_USER}:${COMFY_USER}" "${CKPT_PATH}"
else
  echo "Checkpoint already present (${CKPT_BYTES} bytes), skipping download."
fi

cat >/etc/systemd/system/comfyui.service <<EOF
[Unit]
Description=ComfyUI (127.0.0.1:8188) for Immersive Labs studio-worker
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${COMFY_USER}
Group=${COMFY_USER}
WorkingDirectory=${COMFY_ROOT}
Environment=PYTHONUNBUFFERED=1
# --cpu: e2/CPU-only VMs have no CUDA; without this ComfyUI crashes in model_management (torch.cuda).
ExecStart=${VENV}/bin/python main.py --cpu --listen 127.0.0.1 --port 8188
Restart=on-failure
RestartSec=15

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable comfyui.service
systemctl restart comfyui.service

echo "Waiting for ComfyUI to listen on 8188…"
for _ in $(seq 1 120); do
  if curl -fsS "http://127.0.0.1:8188/system_stats" >/dev/null 2>&1; then
    echo "ComfyUI OK (local /system_stats)."
    exit 0
  fi
  sleep 2
done
echo "ComfyUI did not become ready in time; check: journalctl -u comfyui -n 80 --no-pager"
exit 1

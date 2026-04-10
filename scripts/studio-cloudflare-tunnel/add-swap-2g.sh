#!/usr/bin/env bash
# Run ON the GCP VM once before docker build if builds OOM.
set -euo pipefail

if [[ -f /swapfile ]]; then
  echo "/swapfile already exists; nothing to do."
  exit 0
fi

sudo fallocate -l 2G /swapfile 2>/dev/null || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048 status=progress
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
echo "2G swap enabled."

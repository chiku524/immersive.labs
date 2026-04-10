#!/usr/bin/env bash
# Run on YOUR LAPTOP with gcloud installed and authenticated:
#   gcloud auth login
#   gcloud config set project YOUR_PROJECT_ID
#
# Creates one e2-micro + firewall rule allowing SSH to instances with tag immersive-studio-ssh.
# Adjust ZONE / VM_NAME / DISK_GB as needed.

set -euo pipefail

PROJECT="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
if [[ -z "${PROJECT}" || "${PROJECT}" == "(unset)" ]]; then
  echo "Set project: gcloud config set project YOUR_PROJECT_ID" >&2
  exit 1
fi

ZONE="${ZONE:-us-central1-a}"
VM_NAME="${VM_NAME:-immersive-studio-worker}"
DISK_GB="${DISK_GB:-30}"
NETWORK="${NETWORK:-default}"

echo "Project: ${PROJECT}  Zone: ${ZONE}  VM: ${VM_NAME}"

if gcloud compute instances describe "${VM_NAME}" --zone="${ZONE}" --project="${PROJECT}" >/dev/null 2>&1; then
  echo "Instance ${VM_NAME} already exists in ${ZONE}. Skipping create."
else
  gcloud compute instances create "${VM_NAME}" \
    --project="${PROJECT}" \
    --zone="${ZONE}" \
    --machine-type=e2-micro \
    --boot-disk-size="${DISK_GB}GB" \
    --boot-disk-type=pd-standard \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --tags=immersive-studio-ssh
fi

RULE="immersive-studio-allow-ssh"
if gcloud compute firewall-rules describe "${RULE}" --project="${PROJECT}" >/dev/null 2>&1; then
  echo "Firewall rule ${RULE} already exists."
else
  gcloud compute firewall-rules create "${RULE}" \
    --project="${PROJECT}" \
    --network="${NETWORK}" \
    --direction=INGRESS \
    --action=ALLOW \
    --rules=tcp:22 \
    --source-ranges=0.0.0.0/0 \
    --target-tags=immersive-studio-ssh \
    --description="SSH for immersive studio worker VM (tunnel: no 443/8787 needed)"
fi

echo "SSH:"
echo "  gcloud compute ssh ${VM_NAME} --zone=${ZONE} --project=${PROJECT}"

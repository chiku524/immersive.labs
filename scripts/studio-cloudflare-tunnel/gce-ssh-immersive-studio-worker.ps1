#Requires -Version 5.1
# Open an SSH session to immersive-studio-worker via IAP, using Windows OpenSSH (not PuTTY).
# Run from any directory:
#   powershell -ExecutionPolicy Bypass -File scripts/studio-cloudflare-tunnel/gce-ssh-immersive-studio-worker.ps1
#
# One-time (recommended): System → Environment Variables → User → New
#   Name:  CLOUDSDK_COMPUTE_SSH_WITH_NATIVE_OPENSSH
#   Value: 1
# Then reopen PowerShell so gcloud uses ssh.exe instead of plink.exe.

$ErrorActionPreference = "Stop"
$env:CLOUDSDK_COMPUTE_SSH_WITH_NATIVE_OPENSSH = "1"
$Project = "immersive-labs-studio"
$Zone = "us-central1-a"
$Instance = "immersive-studio-worker"

Write-Host "Using native OpenSSH for gcloud (CLOUDSDK_COMPUTE_SSH_WITH_NATIVE_OPENSSH=1)"
gcloud compute ssh "${Instance}" --zone="${Zone}" --project="${Project}" --tunnel-through-iap

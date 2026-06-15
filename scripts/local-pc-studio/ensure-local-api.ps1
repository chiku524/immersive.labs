#Requires -Version 5.1
# Start local Studio API if not already on :8787. From repo root:
#   .\scripts\local-pc-studio\ensure-local-api.ps1
#
# Windows default: native venv (best Comfy reachability at 127.0.0.1:8188).
# Docker API:  .\scripts\local-pc-studio\ensure-local-api.ps1 -UseDocker
param([switch]$UseDocker)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root

function Test-StudioHealth {
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8787/api/studio/health" -UseBasicParsing -TimeoutSec 3
    return $r.StatusCode -eq 200
  } catch {
    return $false
  }
}

if (Test-StudioHealth) {
  Write-Host "Studio API already running on http://127.0.0.1:8787"
  exit 0
}

if ($UseDocker) {
  Write-Host "Starting studio-worker via Docker Compose ..."
  Write-Host "Comfy: run with COMFYUI_DOCKER_WORKER=1 so Comfy listens on 0.0.0.0:8188"
  docker compose -f (Join-Path $PSScriptRoot "docker-compose.local.yml") up -d --build
} else {
  Write-Host "Starting studio-worker natively (recommended on Windows for Comfy on 127.0.0.1:8188) ..."
  $venvPy = Join-Path $Root "apps\studio-worker\.venv\Scripts\python.exe"
  if (-not (Test-Path $venvPy)) {
    Write-Host "No venv — run .\scripts\local-pc-studio\setup-local-studio.ps1 first (without -UseDocker)"
    exit 1
  }
  Start-Process powershell -ArgumentList @(
    "-NoExit", "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $PSScriptRoot "start-studio-api.ps1")
  ) -WorkingDirectory $Root.Path
}

Start-Sleep -Seconds 5
for ($i = 0; $i -lt 12; $i++) {
  if (Test-StudioHealth) {
    Write-Host "OK: http://127.0.0.1:8787/api/studio/health"
    exit 0
  }
  Start-Sleep -Seconds 2
}
Write-Error "Studio API did not become healthy on :8787"

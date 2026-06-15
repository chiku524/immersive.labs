#Requires -Version 5.1
# Studio API via Docker (Comfy/Ollama on host). From repo root:
#   .\scripts\local-pc-studio\start-studio-api-docker.ps1
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root
$compose = Join-Path $PSScriptRoot "docker-compose.local.yml"
if (-not (Test-Path (Join-Path $Root "apps\studio-worker\.env.local"))) {
  Write-Host "Run setup-local-studio.ps1 -UseDocker first (or create apps/studio-worker/.env.local)."
}
docker compose -f $compose up --build

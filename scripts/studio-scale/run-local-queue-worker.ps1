# Run a queue worker on this Windows machine (local Ollama/Comfy/Blender).
# Usage: .\scripts\studio-scale\run-local-queue-worker.ps1

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$EnvFile = if ($env:STUDIO_SCALE_ENV) { $env:STUDIO_SCALE_ENV } else { Join-Path $Root "apps\studio-worker\.env.scale" }

if (-not (Test-Path $EnvFile)) {
  Write-Error "Missing $EnvFile — copy apps\studio-worker\.env.scale.example"
}

Get-Content $EnvFile | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  if ($_ -match '^\s*([^=]+)=(.*)$') {
    $name = $matches[1].Trim()
    $val = $matches[2].Trim().Trim('"').Trim("'")
    Set-Item -Path "env:$name" -Value $val
  }
}

$env:STUDIO_EMBEDDED_QUEUE_WORKER = "0"
if (-not $env:STUDIO_QUEUE_BACKEND) { $env:STUDIO_QUEUE_BACKEND = "postgres" }
if (-not $env:STUDIO_TENANTS_BACKEND) { $env:STUDIO_TENANTS_BACKEND = "postgres" }

Push-Location (Join-Path $Root "apps\studio-worker")
python -m pip install -e ".[scale]" -q
immersive-studio init-db
immersive-studio doctor --api-only
$doc = immersive-studio doctor 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Warning "Comfy/Blender not fully ready — mock jobs may still work.`n$doc"
}

$wid = if ($env:STUDIO_QUEUE_WORKER_ID) { $env:STUDIO_QUEUE_WORKER_ID } else { "local-gpu-1" }
$poll = if ($env:STUDIO_QUEUE_POLL_INTERVAL) { $env:STUDIO_QUEUE_POLL_INTERVAL } else { "1" }
Write-Host "`nStarting queue worker $wid …"
immersive-studio queue-worker --worker-id $wid --poll-interval $poll

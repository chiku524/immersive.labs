#Requires -Version 5.1
<#
  Free local Immersive Studio (Ollama + Blender on this PC, no cloud VM / no Tripo).

  From repo root:
    .\scripts\local-pc-studio\start-free-local-studio.ps1

  Opens:
    1) Studio API (native venv on :8787) — uses apps/studio-worker/.env.local
    2) Optional second window: npm run dev for http://localhost:5173/studio

  Before full jobs with textures, start Comfy in another terminal:
    .\scripts\local-pc-studio\start-comfyui.ps1
#>
param(
  [switch]$SkipWeb,
  [switch]$NoDockerStop
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root

Write-Host "=== Immersive Studio — free local stack ===" -ForegroundColor Cyan

if (-not $NoDockerStop) {
  $compose = Join-Path $PSScriptRoot "docker-compose.local.yml"
  if (Test-Path $compose) {
    docker compose -f $compose down 2>$null
    Write-Host "Stopped Docker studio-worker (native API uses host Blender + Ollama)."
  }
}

& (Join-Path $PSScriptRoot "setup-local-studio.ps1") -SkipNpm

$EnvLocal = Join-Path $Root "apps\studio-worker\.env.local"
if (-not (Test-Path $EnvLocal)) {
  Write-Error "Missing $EnvLocal — copy scripts/local-pc-studio/env.studio-worker.local.template"
}

$venvPy = Join-Path $Root "apps\studio-worker\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
  Write-Error "Python venv missing. Re-run setup-local-studio.ps1"
}

Write-Host "Running immersive-studio doctor ..."
& $venvPy -m studio_worker.cli doctor 2>&1 | ForEach-Object { Write-Host $_ }
if ($LASTEXITCODE -ne 0) {
  Write-Warning "Doctor reported issues — fix Ollama/Blender/Comfy before full jobs."
}

try {
  $h = Invoke-WebRequest -Uri "http://127.0.0.1:8787/api/studio/health" -UseBasicParsing -TimeoutSec 2
  if ($h.StatusCode -eq 200) {
    Write-Host "Studio API already on :8787 — opening web only."
  }
} catch {
  Write-Host "Starting Studio API in a new window ..."
  Start-Process powershell -ArgumentList @(
    "-NoExit", "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $PSScriptRoot "start-studio-api.ps1")
  ) -WorkingDirectory $Root.Path
  Start-Sleep -Seconds 4
}

if (-not $SkipWeb) {
  Write-Host "Starting Vite dev server in a new window ..."
  Start-Process powershell -ArgumentList @(
    "-NoExit", "-ExecutionPolicy", "Bypass",
    "-Command", "cd '$($Root.Path)'; npm run dev"
  ) -WorkingDirectory $Root.Path
}

Write-Host ""
Write-Host "Open: http://localhost:5173/studio" -ForegroundColor Green
Write-Host "Mock OFF + Export mesh ON for full free jobs (Ollama spec + Blender GLB)."
Write-Host "Textures: start ComfyUI separately (start-comfyui.ps1) then enable Generate textures."

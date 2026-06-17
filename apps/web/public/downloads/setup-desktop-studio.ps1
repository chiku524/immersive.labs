#Requires -Version 5.1
<#
  One-time setup for Immersive Studio **desktop app** (no git clone required).

  Run after installing the desktop app:
    Right-click this file → Run with PowerShell
  Or from PowerShell:
    irm https://immersivelabs.space/downloads/setup-desktop-studio.ps1 | iex

  Creates:
    %LOCALAPPDATA%\Immersive Studio\worker-venv   (pip install immersive-studio)
    %LOCALAPPDATA%\Immersive Studio\worker.env      (Ollama, Blender, Comfy URLs)
    %LOCALAPPDATA%\Immersive Studio\data\           (jobs, queue DB)
#>
$ErrorActionPreference = "Stop"

$AppDir = Join-Path $env:LOCALAPPDATA "Immersive Studio"
$VenvDir = Join-Path $AppDir "worker-venv"
$EnvFile = Join-Path $AppDir "worker.env"
$DataDir = Join-Path $AppDir "data"

New-Item -ItemType Directory -Force -Path $AppDir, $DataDir | Out-Null

Write-Host "=== Immersive Studio desktop worker setup ===" -ForegroundColor Cyan
Write-Host "App data: $AppDir"

$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) {
  Write-Error "Python 3.11+ not found on PATH. Install from https://www.python.org/downloads/ (check 'Add to PATH'), then re-run this script."
}

$venvPy = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
  Write-Host "Creating worker venv ..."
  & python -m venv $VenvDir
}

Write-Host "Installing immersive-studio from PyPI ..."
& $venvPy -m pip install -q -U pip
& $venvPy -m pip install -q "immersive-studio[dev]"

$blenderBin = $env:STUDIO_BLENDER_BIN
if (-not $blenderBin) {
  $candidates = @(
    "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
    "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
    "C:\Program Files\Blender Foundation\Blender 4.1\blender.exe"
  )
  foreach ($c in $candidates) {
    if (Test-Path $c) {
      $blenderBin = $c
      break
    }
  }
}
if (-not $blenderBin) {
  $blenderBin = "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
  Write-Host "Blender not auto-detected — edit worker.env and set STUDIO_BLENDER_BIN after install." -ForegroundColor Yellow
}

$dataDirUnix = $DataDir -replace '\\', '/'
$blenderUnix = $blenderBin -replace '\\', '/'

@"
STUDIO_WORKER_DATA_DIR=$dataDirUnix
STUDIO_OLLAMA_URL=http://127.0.0.1:11434
STUDIO_OLLAMA_MODEL=llama3.2
STUDIO_MESH_PROVIDER=blender_placeholder
STUDIO_BLENDER_BIN=$blenderUnix
STUDIO_COMFY_URL=http://127.0.0.1:8188
STUDIO_EMBEDDED_QUEUE_WORKER=1
"@ | Set-Content -Path $EnvFile -Encoding utf8

Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Green
Write-Host "Launch Immersive Studio from the Start menu."
Write-Host "Optional: ollama pull llama3.2  (real specs when Mock is off in Studio)"
Write-Host "Optional: start ComfyUI on :8188 for textures (see docs on immersivelabs.space)"
Write-Host ""
Write-Host "Worker config: $EnvFile"
Write-Host "Job data:      $DataDir"

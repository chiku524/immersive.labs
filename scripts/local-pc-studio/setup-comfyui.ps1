#Requires -Version 5.1
<#
  Bootstrap ComfyUI for Immersive Studio (venv, CPU PyTorch, SD1.5 checkpoint).

  Usage (from monorepo root):
    .\scripts\local-pc-studio\setup-comfyui.ps1
    .\scripts\local-pc-studio\setup-comfyui.ps1 -ComfyRoot "C:\ComfyUI"

  Env:
    COMFYUI_ROOT — folder containing main.py (default: sibling ComfyUI next to repo)
#>
param(
  [string]$ComfyRoot = "",
  [switch]$SkipModelDownload,
  [switch]$UseGpuTorch
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

if (-not $ComfyRoot) {
  if ($env:COMFYUI_ROOT) {
    $ComfyRoot = $env:COMFYUI_ROOT.TrimEnd('\', '/')
  } else {
    $ComfyRoot = Join-Path (Split-Path $RepoRoot -Parent) "ComfyUI"
  }
}

if (-not (Test-Path (Join-Path $ComfyRoot "main.py"))) {
  Write-Host "Cloning ComfyUI into $ComfyRoot ..."
  git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git $ComfyRoot
}

$VenvDir = Join-Path $ComfyRoot ".venv"
$VenvPy = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
  Write-Host "Creating ComfyUI venv ..."
  python -m venv $VenvDir
}

Write-Host "Installing ComfyUI dependencies (this can take several minutes) ..."
& $VenvPy -m pip install -q -U pip wheel
if ($UseGpuTorch) {
  & $VenvPy -m pip install -q -r (Join-Path $ComfyRoot "requirements.txt")
} else {
  & $VenvPy -m pip install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
  & $VenvPy -m pip install -q -r (Join-Path $ComfyRoot "requirements.txt")
}

$CheckpointDir = Join-Path $ComfyRoot "models\checkpoints"
New-Item -ItemType Directory -Force -Path $CheckpointDir | Out-Null
$CheckpointName = "v1-5-pruned-emaonly.safetensors"
$CheckpointPath = Join-Path $CheckpointDir $CheckpointName

if (-not $SkipModelDownload -and -not (Test-Path $CheckpointPath)) {
  $url = "https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors"
  Write-Host "Downloading SD 1.5 checkpoint (~4 GB) to $CheckpointPath ..."
  Write-Host "This is a one-time download."
  Invoke-WebRequest -Uri $url -OutFile $CheckpointPath -UseBasicParsing
}

$comfyUnix = $ComfyRoot -replace '\\', '/'
Write-Host ""
Write-Host "=== ComfyUI ready ===" -ForegroundColor Green
Write-Host "COMFYUI_ROOT=$comfyUnix"
Write-Host "Checkpoint: $CheckpointPath"
Write-Host "Start: .\scripts\local-pc-studio\start-comfyui.ps1"
if (-not $UseGpuTorch) {
  Write-Host "Using CPU PyTorch. Set COMFYUI_USE_GPU=1 in worker.env after installing CUDA PyTorch." -ForegroundColor Yellow
}

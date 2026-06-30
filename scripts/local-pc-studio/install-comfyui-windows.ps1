#Requires -Version 5.1
<#
  One-time ComfyUI install for local Immersive Studio (Windows).
  From repo root:  .\scripts\local-pc-studio\install-comfyui-windows.ps1
#>
param(
  [string]$ComfyRoot = "",
  [switch]$CpuOnly
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

$ComfyRootWin = $ComfyRoot -replace '/', '\'

Write-Host "=== ComfyUI install for Immersive Studio ===" -ForegroundColor Cyan
Write-Host "Target: $ComfyRootWin"

if (-not (Test-Path (Join-Path $ComfyRootWin "main.py"))) {
  Write-Host "Cloning ComfyUI (shallow) ..."
  New-Item -ItemType Directory -Force -Path (Split-Path $ComfyRootWin -Parent) | Out-Null
  git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git $ComfyRootWin
} else {
  Write-Host "ComfyUI already present"
}

$py312 = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
if (-not $py312) {
  Write-Error "Python 3.12 required. Install from python.org."
}

$VenvDir = Join-Path $ComfyRootWin ".venv"
$VenvPy = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
  Write-Host "Creating venv with Python 3.12 ..."
  & $py312 -m venv $VenvDir
}

& $VenvPy -m pip install -q -U pip wheel

$useGpu = -not $CpuOnly
if ($useGpu -and -not ($env:COMFYUI_USE_GPU -eq "0")) {
  $nvidia = Get-Command nvidia-smi -ErrorAction SilentlyContinue
  if ($nvidia) {
    $env:COMFYUI_USE_GPU = "1"
  } else {
    $useGpu = $false
  }
}

if ($env:COMFYUI_USE_GPU -eq "1") {
  Write-Host "Installing PyTorch CUDA cu124 ..."
  & $VenvPy -m pip install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
} else {
  Write-Host "Installing PyTorch CPU ..."
  & $VenvPy -m pip install -q torch torchvision torchaudio
}

Write-Host "Installing ComfyUI requirements ..."
& $VenvPy -m pip install -q -r (Join-Path $ComfyRootWin "requirements.txt")

$CkptDir = Join-Path $ComfyRootWin "models\checkpoints"
New-Item -ItemType Directory -Force -Path $CkptDir | Out-Null
$CkptName = "v1-5-pruned-emaonly.safetensors"
$CkptPath = Join-Path $CkptDir $CkptName
if (-not (Test-Path $CkptPath)) {
  $CkptUrl = "https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive/resolve/main/v1-5-pruned-emaonly.safetensors"
  Write-Host "Downloading checkpoint (about 4 GB) ..."
  curl.exe -L --retry 3 --continue-at - -o $CkptPath $CkptUrl
} else {
  Write-Host "Checkpoint already present"
}

$WorkerEnv = Join-Path $env:LOCALAPPDATA "Immersive Studio\worker.env"
$comfyUnix = $ComfyRootWin -replace '\\', '/'
if (Test-Path $WorkerEnv) {
  $lines = Get-Content $WorkerEnv | Where-Object {
    $_ -notmatch '^\s*COMFYUI_ROOT=' -and $_ -notmatch '^\s*STUDIO_COMFY_CHECKPOINT='
  }
  @($lines + "COMFYUI_ROOT=$comfyUnix" + "STUDIO_COMFY_CHECKPOINT=$CkptName") | Set-Content $WorkerEnv -Encoding utf8
  Write-Host "Updated worker.env"
}

Write-Host "=== ComfyUI install done ===" -ForegroundColor Green
Write-Host "Run: .\scripts\local-pc-studio\start-desktop-services.ps1"

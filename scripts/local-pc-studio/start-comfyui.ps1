#Requires -Version 5.1
<#
  Start ComfyUI for local Studio (listens on 127.0.0.1:8188).
  Usage (from monorepo root):  .\scripts\local-pc-studio\start-comfyui.ps1

  COMFYUI_ROOT     - folder that contains main.py (default: sibling folder ComfyUI next to this repo).
  COMFYUI_USE_GPU  - set to 1 if you installed CUDA PyTorch; omits --cpu (required for CPU-only torch).

  On Windows, tqdm can throw [Errno 22] Invalid argument during KSampler when stderr is not a real
  console (some IDEs / background shells). We set TQDM_DISABLE=1 unless you already exported it to 0.
#>
$ErrorActionPreference = "Stop"
if (-not ($env:TQDM_DISABLE -eq "0")) {
  $env:TQDM_DISABLE = "1"
}
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if ($env:COMFYUI_ROOT) {
  $ComfyRoot = $env:COMFYUI_ROOT.TrimEnd('\', '/')
} else {
  $ComfyRoot = Join-Path (Split-Path $RepoRoot -Parent) "ComfyUI"
}
if (-not (Test-Path (Join-Path $ComfyRoot "main.py"))) {
  Write-Error "ComfyUI not found at '$ComfyRoot'. Clone ComfyUI there or set COMFYUI_ROOT."
}
$VenvPy = Join-Path $ComfyRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
  Write-Error "Missing $VenvPy - create a venv in ComfyUI and pip install -r requirements.txt"
}
$cpuArg = @()
if (-not ($env:COMFYUI_USE_GPU -eq "1")) {
  $cpuArg = @("--cpu")
}
Set-Location $ComfyRoot
$gpuMode = if ($env:COMFYUI_USE_GPU -eq "1") { "yes" } else { "no" }
Write-Host "Starting ComfyUI from $ComfyRoot (GPU mode: $gpuMode)"
& $VenvPy main.py --listen 127.0.0.1 --port 8188 @cpuArg @args

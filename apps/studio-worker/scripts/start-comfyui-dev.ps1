# Start ComfyUI for local studio texture jobs (listens on 127.0.0.1:8188).
# Prereq: clone https://github.com/comfyanonymous/ComfyUI and install its Python deps.
#
# Usage:
#   $env:COMFYUI_ROOT = "C:\path\to\ComfyUI"
#   .\scripts\start-comfyui-dev.ps1
#
# Then in another terminal: immersive-studio doctor

$ErrorActionPreference = "Stop"
if (-not $env:COMFYUI_ROOT) {
    Write-Host "Set COMFYUI_ROOT to your ComfyUI repository path, e.g.:"
    Write-Host '  $env:COMFYUI_ROOT = "C:\src\ComfyUI"'
    exit 1
}
$root = $env:COMFYUI_ROOT
if (-not (Test-Path (Join-Path $root "main.py"))) {
    Write-Host "COMFYUI_ROOT does not look like ComfyUI (missing main.py): $root"
    exit 1
}
Set-Location $root
python main.py --listen 127.0.0.1 --port 8188

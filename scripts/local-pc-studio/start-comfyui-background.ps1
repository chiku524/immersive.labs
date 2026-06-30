#Requires -Version 5.1
<#
  Start ComfyUI in the background (no console flash) for desktop / local Studio.
  Usage: .\scripts\local-pc-studio\start-comfyui-background.ps1
#>
$ErrorActionPreference = "Stop"
if (-not ($env:TQDM_DISABLE -eq "0")) {
  $env:TQDM_DISABLE = "1"
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$WorkerEnv = Join-Path $env:LOCALAPPDATA "Immersive Studio\worker.env"

function Read-WorkerEnvValue([string]$Key) {
  if (-not (Test-Path $WorkerEnv)) { return $null }
  foreach ($line in Get-Content $WorkerEnv) {
    $t = $line.Trim()
    if ($t -match "^\s*#") { continue }
    if ($t -match "^$Key=(.*)$") { return $Matches[1].Trim() }
  }
  return $null
}

if ($env:COMFYUI_ROOT) {
  $ComfyRoot = $env:COMFYUI_ROOT.TrimEnd('\', '/')
} elseif (Read-WorkerEnvValue "COMFYUI_ROOT") {
  $ComfyRoot = (Read-WorkerEnvValue "COMFYUI_ROOT")
} else {
  $ComfyRoot = Join-Path (Split-Path $RepoRoot -Parent) "ComfyUI"
}

if (-not (Test-Path (Join-Path $ComfyRoot "main.py"))) {
  Write-Error "ComfyUI not found at '$ComfyRoot'. Run .\scripts\local-pc-studio\setup-comfyui.ps1 first."
}

try {
  $null = Invoke-WebRequest -Uri "http://127.0.0.1:8188/system_stats" -UseBasicParsing -TimeoutSec 3
  Write-Host "ComfyUI already running at http://127.0.0.1:8188"
  exit 0
} catch {
  # not running
}

$VenvPyw = Join-Path $ComfyRoot ".venv\Scripts\pythonw.exe"
$VenvPy = Join-Path $ComfyRoot ".venv\Scripts\python.exe"
$Launcher = if (Test-Path $VenvPyw) { $VenvPyw } else { $VenvPy }

$useGpu = $env:COMFYUI_USE_GPU
if (-not $useGpu) { $useGpu = Read-WorkerEnvValue "COMFYUI_USE_GPU" }
$cpuArg = if ($useGpu -eq "1") { @() } else { @("--cpu") }

$logDir = Join-Path $env:LOCALAPPDATA "Immersive Studio"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "comfyui-serve.log"

$argList = @(
  "main.py",
  "--listen", "127.0.0.1",
  "--port", "8188"
) + $cpuArg

Write-Host "Starting ComfyUI ($Launcher) - log: $logFile"
Start-Process -FilePath $Launcher `
  -ArgumentList $argList `
  -WorkingDirectory $ComfyRoot `
  -WindowStyle Hidden `
  -RedirectStandardError $logFile

for ($i = 0; $i -lt 60; $i++) {
  Start-Sleep -Seconds 2
  try {
    $null = Invoke-WebRequest -Uri "http://127.0.0.1:8188/system_stats" -UseBasicParsing -TimeoutSec 3
    Write-Host "ComfyUI is up at http://127.0.0.1:8188" -ForegroundColor Green
    exit 0
  } catch {
    # wait
  }
}

Write-Host "ComfyUI did not respond within 120s. Check $logFile" -ForegroundColor Yellow
exit 1

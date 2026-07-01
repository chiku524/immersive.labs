#Requires -Version 5.1
<#
  Start Immersive Studio desktop worker + ComfyUI in hidden background.
  From repo root:  .\scripts\local-pc-studio\start-desktop-services.ps1
#>
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

$AppDir = Join-Path $env:LOCALAPPDATA "Immersive Studio"
$VenvPy = Join-Path $AppDir "worker-venv\Scripts\python.exe"
$VenvPyw = Join-Path $AppDir "worker-venv\Scripts\pythonw.exe"
$EnvFile = Join-Path $AppDir "worker.env"
$LogFile = Join-Path $AppDir "worker-serve.log"

if (-not (Test-Path $VenvPy)) {
  Write-Error "Desktop worker venv missing. Run setup-desktop-studio.ps1 first."
}

function Import-DotEnvFile([string]$Path) {
  if (-not (Test-Path $Path)) { return }
  Get-Content $Path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    if ($line -match '^([^=]+)=(.*)$') {
      $key = $Matches[1].Trim()
      $val = $Matches[2].Trim()
      if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
        $val = $val.Substring(1, $val.Length - 2)
      }
      [Environment]::SetEnvironmentVariable($key, $val, "Process")
    }
  }
}

Import-DotEnvFile $EnvFile

function Test-HttpOk([string]$Url) {
  try {
    $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 4
    return $r.StatusCode -ge 200 -and $r.StatusCode -lt 300
  } catch { return $false }
}

$launcher = if (Test-Path $VenvPyw) { $VenvPyw } else { $VenvPy }

if (-not (Test-HttpOk "http://127.0.0.1:8787/api/studio/health")) {
  Write-Host "Starting Studio API hidden ..."
  $workerArgs = "-m studio_worker.cli serve --host 127.0.0.1 --port 8787"
  Start-Process -FilePath $launcher -ArgumentList $workerArgs -WorkingDirectory $AppDir `
    -WindowStyle Hidden -RedirectStandardError $LogFile
  for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    if (Test-HttpOk "http://127.0.0.1:8787/api/studio/health") { break }
  }
} else {
  Write-Host "Studio API already on port 8787"
}

if (-not (Test-HttpOk "http://127.0.0.1:8188/system_stats")) {
  $ComfyRoot = $env:COMFYUI_ROOT
  if (-not $ComfyRoot) {
    $ComfyRoot = Join-Path (Split-Path $RepoRoot -Parent) "ComfyUI"
  }
  $ComfyPy = Join-Path $ComfyRoot ".venv\Scripts\python.exe"
  $ComfyPyw = Join-Path $ComfyRoot ".venv\Scripts\pythonw.exe"
  if (-not (Test-Path (Join-Path $ComfyRoot "main.py"))) {
    Write-Warning "ComfyUI not found. Run install-comfyui-windows.ps1 first."
  } elseif (-not (Test-Path $ComfyPy)) {
    Write-Warning "ComfyUI venv missing"
  } else {
    $comfyLauncher = if (Test-Path $ComfyPyw) { $ComfyPyw } else { $ComfyPy }
    $comfyLog = Join-Path $AppDir "comfyui-serve.log"
    $gpuOn = ($env:COMFYUI_USE_GPU -eq "1")
    Write-Host "Starting ComfyUI hidden. GPU enabled: $gpuOn"
    $BundledLauncher = Join-Path $RepoRoot "apps\studio-desktop\src-tauri\resources\comfy_silent_launcher.py"
    $AppLauncher = Join-Path $AppDir "comfy_silent_launcher.py"
    if (Test-Path $BundledLauncher) {
      Copy-Item -Force $BundledLauncher $AppLauncher
    }
    if (-not (Test-Path $AppLauncher)) {
      Write-Warning "comfy_silent_launcher.py missing — Comfy may flash consoles"
      $comfyArgs = if ($gpuOn) {
        @("main.py", "--listen", "127.0.0.1", "--port", "8188")
      } else {
        @("main.py", "--listen", "127.0.0.1", "--port", "8188", "--cpu")
      }
    } else {
      $comfyArgs = if ($gpuOn) {
        @($AppLauncher, $ComfyRoot, "--listen", "127.0.0.1", "--port", "8188")
      } else {
        @($AppLauncher, $ComfyRoot, "--listen", "127.0.0.1", "--port", "8188", "--cpu")
      }
    }
    $env:TQDM_DISABLE = "1"
    Start-Process -FilePath $comfyLauncher -ArgumentList $comfyArgs -WorkingDirectory $ComfyRoot `
      -WindowStyle Hidden -RedirectStandardError $comfyLog
    Write-Host "ComfyUI log: $comfyLog"
  }
} else {
  Write-Host "ComfyUI already on port 8188"
}

Write-Host ""
if (Test-HttpOk "http://127.0.0.1:11434/api/tags") {
  Write-Host "Ollama: OK"
} else {
  Write-Host "Ollama: not reachable"
}
if (Test-HttpOk "http://127.0.0.1:8787/api/studio/health") {
  Write-Host "Studio API: OK"
} else {
  Write-Host "Studio API: starting or failed (see worker-serve.log)"
}
if (Test-HttpOk "http://127.0.0.1:8188/system_stats") {
  Write-Host "ComfyUI: OK"
} else {
  Write-Host "ComfyUI: starting or not installed"
}
